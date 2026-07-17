//+------------------------------------------------------------------+
//| RP AI Executor V28 -- minimum execution path                    |
//+------------------------------------------------------------------+
#property strict
#property version   "28.04"
#property description "V28 executor: direct Common Files decision payload execution."

#include <Trade/Trade.mqh>

#define DECISION_PATH "RP_AI_EA\\shared\\XAUUSD\\decision.json"

input double InpExposureCapLots           = 1.00;
input double InpDefaultLot                = 0.01;
input bool   InpEmergencyDisable          = false;
input long   InpMagic                     = 2800001;

CTrade g_trade;

bool IsPayloadTrimCharacter(const ushort character)
{
   return character == ' ' || character == '\t' || character == '\r' ||
          character == '\n' || character == 0 || character == 0xFEFF;
}

string TrimDecisionPayload(string payload)
{
   int first = 0;
   int last = StringLen(payload) - 1;
   while(first <= last && IsPayloadTrimCharacter(StringGetCharacter(payload, first))) first++;
   while(last >= first && IsPayloadTrimCharacter(StringGetCharacter(payload, last))) last--;
   if(first > last) return "";
   return StringSubstr(payload, first, last - first + 1);
}


bool AppendUnicodeCodePoint(string &text, const uint code_point)
{
   if(code_point > 0x10FFFF || (code_point >= 0xD800 && code_point <= 0xDFFF)) return false;
   if(code_point <= 0xFFFF)
   {
      text += CharToString((ushort)code_point);
      return true;
   }

   uint value = code_point - 0x10000;
   text += CharToString((ushort)(0xD800 + (value >> 10)));
   text += CharToString((ushort)(0xDC00 + (value & 0x3FF)));
   return true;
}

bool DecodeUtf8(const uchar &bytes[], const int start, string &text)
{
   text = "";
   int length = ArraySize(bytes);
   for(int index = start; index < length;)
   {
      uint code_point = 0;
      int continuation_count = 0;
      uchar first = bytes[index++];
      if(first < 0x80) code_point = first;
      else if(first >= 0xC2 && first <= 0xDF) { code_point = first & 0x1F; continuation_count = 1; }
      else if(first >= 0xE0 && first <= 0xEF) { code_point = first & 0x0F; continuation_count = 2; }
      else if(first >= 0xF0 && first <= 0xF4) { code_point = first & 0x07; continuation_count = 3; }
      else return false;

      if(index + continuation_count > length) return false;
      for(int count = 0; count < continuation_count; count++)
      {
         uchar next = bytes[index++];
         if((next & 0xC0) != 0x80) return false;
         code_point = (code_point << 6) | (next & 0x3F);
      }
      if((continuation_count == 2 && code_point < 0x800) ||
         (continuation_count == 3 && code_point < 0x10000) ||
         !AppendUnicodeCodePoint(text, code_point)) return false;
   }
   return true;
}

bool DecodeUtf16(const uchar &bytes[], const int start, const bool little_endian, string &text)
{
   text = "";
   int length = ArraySize(bytes);
   if((length - start) % 2 != 0) return false;
   for(int index = start; index < length; index += 2)
   {
      ushort unit = little_endian ? (ushort)(bytes[index] | (bytes[index + 1] << 8))
                                  : (ushort)((bytes[index] << 8) | bytes[index + 1]);
      if(unit >= 0xD800 && unit <= 0xDBFF)
      {
         if(index + 3 >= length) return false;
         ushort low = little_endian ? (ushort)(bytes[index + 2] | (bytes[index + 3] << 8))
                                    : (ushort)((bytes[index + 2] << 8) | bytes[index + 3]);
         if(low < 0xDC00 || low > 0xDFFF) return false;
         uint code_point = 0x10000 + (((uint)unit - 0xD800) << 10) + ((uint)low - 0xDC00);
         if(!AppendUnicodeCodePoint(text, code_point)) return false;
         index += 2;
      }
      else if(unit >= 0xDC00 && unit <= 0xDFFF) return false;
      else text += CharToString(unit);
   }
   return true;
}

bool DecodeDecisionPayload(const uchar &bytes[], string &payload)
{
   int length = ArraySize(bytes);
   if(length >= 3 && bytes[0] == 0xEF && bytes[1] == 0xBB && bytes[2] == 0xBF)
      return DecodeUtf8(bytes, 3, payload);
   if(length >= 2 && bytes[0] == 0xFF && bytes[1] == 0xFE)
      return DecodeUtf16(bytes, 2, true, payload);
   if(length >= 2 && bytes[0] == 0xFE && bytes[1] == 0xFF)
      return DecodeUtf16(bytes, 2, false, payload);

   // decision.json is UTF-8 when no byte-order mark is present.
   return DecodeUtf8(bytes, 0, payload);
}

bool ReadDecisionPayload(string &payload)
{
   ResetLastError();
   int handle = FileOpen(
      "RP_AI_EA\\shared\\XAUUSD\\decision.json",
      FILE_READ | FILE_BIN | FILE_COMMON | FILE_SHARE_READ | FILE_SHARE_WRITE
   );
   if(handle == INVALID_HANDLE)
   {
      Print("DECISION_FILE_OPEN_FAIL | error=", GetLastError(), " | path=", DECISION_PATH);
      return false;
   }

   long file_size = FileSize(handle);
   if(file_size <= 0 || file_size > 1048576)
   {
      FileClose(handle);
      Print(file_size == 0 ? "DECISION_FILE_EMPTY" : "DECISION_FILE_SIZE_INVALID");
      return false;
   }

   uchar bytes[];
   int bytes_read = FileReadArray(handle, bytes, 0, (int)file_size);
   FileClose(handle);
   if(bytes_read != (int)file_size || !DecodeDecisionPayload(bytes, payload))
   {
      Print("DECISION_PAYLOAD_DECODE_FAIL | bytes_read=", bytes_read, " | file_size=", file_size);
      return false;
   }

   payload = TrimDecisionPayload(payload);
   if(payload == "") { Print("DECISION_FILE_EMPTY"); return false; }
   return true;
}

bool IsJsonWhitespace(const ushort character)
{
   return character == ' ' || character == '\t' || character == '\r' || character == '\n';
}

// This is intentionally a field scanner, not a JSON parser.  It only finds a
// quoted key at root-object depth and never validates unrelated payload data.
bool FindTopLevelField(const string json, const string key, int &value_start)
{
   int depth = 0;
   bool in_string = false;
   bool escaped = false;
   int length = StringLen(json);
   for(int index = 0; index < length; index++)
   {
      ushort character = StringGetCharacter(json, index);
      if(in_string)
      {
         if(escaped) { escaped = false; continue; }
         if(character == '\\') { escaped = true; continue; }
         if(character != '"') continue;
         in_string = false;
         continue;
      }

      if(character == '"')
      {
         if(depth == 1 && StringSubstr(json, index + 1, StringLen(key)) == key &&
            index + StringLen(key) + 1 < length && StringGetCharacter(json, index + StringLen(key) + 1) == '"')
         {
            int colon = index + StringLen(key) + 2;
            while(colon < length && IsJsonWhitespace(StringGetCharacter(json, colon))) colon++;
            if(colon < length && StringGetCharacter(json, colon) == ':')
            {
               value_start = colon + 1;
               while(value_start < length && IsJsonWhitespace(StringGetCharacter(json, value_start))) value_start++;
               return value_start < length;
            }
         }
         in_string = true;
      }
      else if(character == '{' || character == '[') depth++;
      else if(character == '}' || character == ']') depth--;
   }
   return false;
}

bool ReadFieldString(const string json, const string key, string &value)
{
   int start = 0;
   if(!FindTopLevelField(json, key, start) || StringGetCharacter(json, start) != '"') return false;
   start++;
   int end = start;
   bool escaped = false;
   while(end < StringLen(json))
   {
      ushort character = StringGetCharacter(json, end);
      if(!escaped && character == '"')
      {
         value = StringSubstr(json, start, end - start);
         return true;
      }
      if(!escaped && character == '\\') escaped = true;
      else escaped = false;
      end++;
   }
   return false;
}

bool ReadFieldNumber(const string json, const string key, double &value)
{
   int start = 0;
   if(!FindTopLevelField(json, key, start)) return false;
   int end = start;
   while(end < StringLen(json))
   {
      ushort character = StringGetCharacter(json, end);
      if((character >= '0' && character <= '9') || character == '-' || character == '+' ||
         character == '.' || character == 'e' || character == 'E') end++;
      else break;
   }
   if(end == start) return false;
   value = StringToDouble(StringSubstr(json, start, end - start));
   return true;
}

bool ReadFieldBool(const string json, const string key, bool &value)
{
   int start = 0;
   if(!FindTopLevelField(json, key, start)) return false;
   string literal = StringSubstr(json, start, 5);
   StringToLower(literal);
   if(StringSubstr(literal, 0, 4) == "true") { value = true; return true; }
   if(literal == "false") { value = false; return true; }
   return false;
}

bool ValidLot(const string symbol, const double lot, string &reason)
{
   double minimum = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   double maximum = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   double step = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   if(lot < minimum || lot > maximum || step <= 0.0)
   {
      reason = "INVALID_LOT";
      return false;
   }
   double steps = (lot - minimum) / step;
   if(MathAbs(steps - MathRound(steps)) > 0.0000001)
   {
      reason = "INVALID_LOT_STEP";
      return false;
   }
   return true;
}

double CurrentExposureLots(const string symbol)
{
   double exposure = 0.0;
   for(int index = PositionsTotal() - 1; index >= 0; --index)
   {
      ulong ticket = PositionGetTicket(index);
      if(ticket > 0 && PositionGetString(POSITION_SYMBOL) == symbol)
         exposure += PositionGetDouble(POSITION_VOLUME);
   }
   return exposure;
}

bool BrokerSafetyPass(const string symbol, const string action, const double lot, string &reason)
{
   if(symbol == "" || symbol != _Symbol || !SymbolSelect(symbol, true))
   {
      reason = "INVALID_SYMBOL";
      return false;
   }
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) || !MQLInfoInteger(MQL_TRADE_ALLOWED))
   {
      reason = "BROKER_TRADING_DISABLED";
      return false;
   }
   if(!ValidLot(symbol, lot, reason)) return false;
   if(InpExposureCapLots <= 0.0 || CurrentExposureLots(symbol) + lot > InpExposureCapLots)
   {
      reason = "EXPOSURE_CAP_EXCEEDED";
      return false;
   }

   MqlTick tick;
   if(!SymbolInfoTick(symbol, tick))
   {
      reason = "BROKER_TICK_UNAVAILABLE";
      return false;
   }
   double margin = 0.0;
   ENUM_ORDER_TYPE order_type = action == "BUY" ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   double price = action == "BUY" ? tick.ask : tick.bid;
   if(!OrderCalcMargin(order_type, symbol, lot, price, margin) || margin <= 0.0 ||
      AccountInfoDouble(ACCOUNT_FREEMARGIN) < margin)
   {
      reason = "INSUFFICIENT_MARGIN";
      return false;
   }
   return true;
}

void OnTick()
{
   if(InpEmergencyDisable) { Print("EMERGENCY_DISABLE_ACTIVE"); return; }

   string json;
   if(!ReadDecisionPayload(json)) return;

   string decision = "";
   if(!ReadFieldString(json, "decision", decision))
   {
      Print("DECISION_REQUIRED_FIELD_MISSING | field=decision");
      return;
   }

   string action = "";
   if(!ReadFieldString(json, "action", action))
      if(!ReadFieldString(json, "direction", action))
         ReadFieldString(json, "bias", action);
   StringToUpper(action);
   bool entry_allowed = false;
   ReadFieldBool(json, "entry_allowed", entry_allowed);

   double lot = InpDefaultLot;
   ReadFieldNumber(json, "lot", lot);
   double tp = 0.0;
   if(!ReadFieldNumber(json, "take_profit", tp))
      if(!ReadFieldNumber(json, "tp", tp))
         ReadFieldNumber(json, "tp1", tp);

   PrintFormat("DECISION_FIELDS_OK | decision=%s | action=%s | entry_allowed=%s | lot=%s | tp=%s",
               decision, action, entry_allowed ? "true" : "false", DoubleToString(lot, 2), DoubleToString(tp, _Digits));
   if(decision != "TRADE" || !entry_allowed)
   {
      PrintFormat("DECISION_SKIP | decision=%s | entry_allowed=%s | action=%s",
                  decision, entry_allowed ? "true" : "false", action);
      return;
   }

   if(action != "BUY" && action != "SELL") { Print("INVALID_ACTION"); return; }

   string reason;
   string symbol = _Symbol;
   if(!BrokerSafetyPass(symbol, action, lot, reason)) { Print(reason); return; }

   string comment = "RP_V28";
   g_trade.SetExpertMagicNumber(InpMagic);

   // SL is permanently disabled.  This executor never modifies a position.
   PrintFormat("ORDER_SEND_ATTEMPT | side=%s | lot=%s | sl=0 | tp=%s",
               action, DoubleToString(lot, 2), DoubleToString(tp, _Digits));
   ResetLastError();
   bool sent = false;
   if(action == "BUY")
      sent = g_trade.Buy(lot, symbol, 0.0, 0.0, tp, comment);
   else
      sent = g_trade.Sell(lot, symbol, 0.0, 0.0, tp, comment);

   if(sent)
      PrintFormat("ORDER_SEND_OK | ticket=%I64u | side=%s | sl=0", g_trade.ResultOrder(), action);
   else
      PrintFormat("ORDER_SEND_FAIL | retcode=%u | description=%s | last_error=%d",
                  g_trade.ResultRetcode(), g_trade.ResultRetcodeDescription(), GetLastError());
}
