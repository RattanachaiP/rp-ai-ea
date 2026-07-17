//+------------------------------------------------------------------+
//| RP AI Executor V28 -- minimum execution path                    |
//+------------------------------------------------------------------+
#property strict
#property version   "28.03"
#property description "V28 executor: direct Common Files decision payload execution."

#include <Trade/Trade.mqh>

#define DECISION_PATH "RP_AI_EA\\shared\\XAUUSD\\decision.json"

input double InpExposureCapLots           = 1.00;
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

void SkipJsonWhitespace(const string json, int &position)
{
   while(position < StringLen(json))
   {
      ushort character = StringGetCharacter(json, position);
      if(character != ' ' && character != '\t' && character != '\r' && character != '\n') break;
      position++;
   }
}

bool ParseJsonValue(const string json, int &position);

bool ParseJsonString(const string json, int &position)
{
   if(position >= StringLen(json) || StringGetCharacter(json, position) != '"') return false;
   position++;
   while(position < StringLen(json))
   {
      ushort character = StringGetCharacter(json, position++);
      if(character == '"') return true;
      if(character < 0x20) return false;
      if(character != '\\') continue;
      if(position >= StringLen(json)) return false;
      ushort escaped = StringGetCharacter(json, position++);
      if(escaped == '"' || escaped == '\\' || escaped == '/' || escaped == 'b' ||
         escaped == 'f' || escaped == 'n' || escaped == 'r' || escaped == 't') continue;
      if(escaped != 'u' || position + 4 > StringLen(json)) return false;
      for(int index = 0; index < 4; index++)
      {
         ushort hex = StringGetCharacter(json, position++);
         if(!((hex >= '0' && hex <= '9') || (hex >= 'a' && hex <= 'f') ||
              (hex >= 'A' && hex <= 'F'))) return false;
      }
   }
   return false;
}

bool ParseJsonNumber(const string json, int &position)
{
   int length = StringLen(json);
   if(position < length && StringGetCharacter(json, position) == '-') position++;
   int digits_start = position;
   if(position < length && StringGetCharacter(json, position) == '0') position++;
   else while(position < length && StringGetCharacter(json, position) >= '1' && StringGetCharacter(json, position) <= '9') position++;
   if(position == digits_start) return false;
   if(position < length && StringGetCharacter(json, position) == '.')
   {
      position++;
      int fraction_start = position;
      while(position < length && StringGetCharacter(json, position) >= '0' && StringGetCharacter(json, position) <= '9') position++;
      if(position == fraction_start) return false;
   }
   if(position < length && (StringGetCharacter(json, position) == 'e' || StringGetCharacter(json, position) == 'E'))
   {
      position++;
      if(position < length && (StringGetCharacter(json, position) == '+' || StringGetCharacter(json, position) == '-')) position++;
      int exponent_start = position;
      while(position < length && StringGetCharacter(json, position) >= '0' && StringGetCharacter(json, position) <= '9') position++;
      if(position == exponent_start) return false;
   }
   return true;
}

bool ParseJsonObject(const string json, int &position)
{
   position++;
   SkipJsonWhitespace(json, position);
   if(position < StringLen(json) && StringGetCharacter(json, position) == '}') { position++; return true; }
   while(position < StringLen(json))
   {
      if(!ParseJsonString(json, position)) return false;
      SkipJsonWhitespace(json, position);
      if(position >= StringLen(json) || StringGetCharacter(json, position++) != ':') return false;
      SkipJsonWhitespace(json, position);
      if(!ParseJsonValue(json, position)) return false;
      SkipJsonWhitespace(json, position);
      if(position < StringLen(json) && StringGetCharacter(json, position) == '}') { position++; return true; }
      if(position >= StringLen(json) || StringGetCharacter(json, position++) != ',') return false;
      SkipJsonWhitespace(json, position);
   }
   return false;
}

bool ParseJsonArray(const string json, int &position)
{
   position++;
   SkipJsonWhitespace(json, position);
   if(position < StringLen(json) && StringGetCharacter(json, position) == ']') { position++; return true; }
   while(position < StringLen(json))
   {
      if(!ParseJsonValue(json, position)) return false;
      SkipJsonWhitespace(json, position);
      if(position < StringLen(json) && StringGetCharacter(json, position) == ']') { position++; return true; }
      if(position >= StringLen(json) || StringGetCharacter(json, position++) != ',') return false;
      SkipJsonWhitespace(json, position);
   }
   return false;
}

bool ParseJsonValue(const string json, int &position)
{
   SkipJsonWhitespace(json, position);
   if(position >= StringLen(json)) return false;
   ushort character = StringGetCharacter(json, position);
   if(character == '{') return ParseJsonObject(json, position);
   if(character == '[') return ParseJsonArray(json, position);
   if(character == '"') return ParseJsonString(json, position);
   if(character == '-' || (character >= '0' && character <= '9')) return ParseJsonNumber(json, position);
   string literal = StringSubstr(json, position, 5);
   if(StringSubstr(literal, 0, 4) == "true") { position += 4; return true; }
   if(StringSubstr(literal, 0, 5) == "false") { position += 5; return true; }
   if(StringSubstr(literal, 0, 4) == "null") { position += 4; return true; }
   return false;
}

bool IsStructurallyValidJson(const string json)
{
   int position = 0;
   if(!ParseJsonValue(json, position)) return false;
   SkipJsonWhitespace(json, position);
   return position == StringLen(json);
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
   if(!IsStructurallyValidJson(payload))
   {
      Print("DECISION_JSON_PARSE_FAIL | payload=", StringSubstr(payload, 0, 300));
      return false;
   }
   return true;
}

string JsonString(const string json, const string key, const string fallback="")
{
   string pattern = "\"" + key + "\"";
   int pos = StringFind(json, pattern);
   if(pos < 0) return fallback;
   int colon = StringFind(json, ":", pos);
   int first = StringFind(json, "\"", colon + 1);
   int second = StringFind(json, "\"", first + 1);
   if(colon < 0 || first < 0 || second < 0) return fallback;
   return StringSubstr(json, first + 1, second - first - 1);
}

double JsonNumber(const string json, const string key, const double fallback=0.0)
{
   string pattern = "\"" + key + "\"";
   int pos = StringFind(json, pattern);
   if(pos < 0) return fallback;
   int colon = StringFind(json, ":", pos);
   if(colon < 0) return fallback;
   int end = colon + 1;
   while(end < StringLen(json))
   {
      ushort ch = StringGetCharacter(json, end);
      if((ch >= '0' && ch <= '9') || ch == '-' || ch == '.' || ch == 'e' || ch == 'E') end++;
      else if(ch == ' ' || ch == '\t') end++;
      else break;
   }
   return StringToDouble(StringSubstr(json, colon + 1, end - colon - 1));
}

bool JsonBool(const string json, const string key, const bool fallback=false)
{
   string pattern = "\"" + key + "\"";
   int pos = StringFind(json, pattern);
   if(pos < 0) return fallback;
   int colon = StringFind(json, ":", pos);
   if(colon < 0) return fallback;
   string tail = StringSubstr(json, colon + 1, 8);
   StringToLower(tail);
   if(StringFind(tail, "true") >= 0) return true;
   if(StringFind(tail, "false") >= 0) return false;
   return fallback;
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

   string decision = JsonString(json, "decision");
   string action = JsonString(json, "action", JsonString(json, "direction"));
   StringToUpper(action);
   bool entry_allowed = JsonBool(json, "entry_allowed");
   Print(json);
   Print("DECISION_PAYLOAD_OK | decision=", decision, " | action=", action, " | entry_allowed=", entry_allowed);
   if(decision != "TRADE" || !entry_allowed) return;

   if(action != "BUY" && action != "SELL") { Print("INVALID_ACTION"); return; }

   string reason;
   string symbol = JsonString(json, "symbol", _Symbol);
   double lot = JsonNumber(json, "lot");
   if(!BrokerSafetyPass(symbol, action, lot, reason)) { Print(reason); return; }

   double tp = JsonNumber(json, "take_profit", JsonNumber(json, "tp", JsonNumber(json, "tp1")));
   string trade_uuid = JsonString(json, "trade_uuid");
   string comment = trade_uuid == "" ? "RP_V28" : StringSubstr(trade_uuid, 0, 24);
   g_trade.SetExpertMagicNumber(InpMagic);

   // SL is permanently disabled.  This executor never modifies a position.
   if(action == "BUY")
   {
      if(g_trade.Buy(lot, symbol, 0, 0, tp, comment)) Print("ORDER_SEND_OK ticket=", g_trade.ResultOrder());
      else Print("ORDER_SEND_FAIL retcode=", g_trade.ResultRetcode(), " description=", g_trade.ResultRetcodeDescription());
   }
   else
   {
      if(g_trade.Sell(lot, symbol, 0, 0, tp, comment)) Print("ORDER_SEND_OK ticket=", g_trade.ResultOrder());
      else Print("ORDER_SEND_FAIL retcode=", g_trade.ResultRetcode(), " description=", g_trade.ResultRetcodeDescription());
   }
}
