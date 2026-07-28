//+------------------------------------------------------------------+
//| RP Governed Executor -- canonical package consumer                    |
//+------------------------------------------------------------------+
#property strict
#property version   "28.05"
#property description "Canonical governed one-shot execution_package.json consumer."

#include <Trade/Trade.mqh>

#define EXECUTION_PACKAGE_PATH "RP_AI_EA\\shared\\XAUUSD\\execution_package.json"

input double InpExposureCapLots           = 1.00;
input bool   InpEmergencyDisable          = false;
input long   InpMagic                     = 2800001;

CTrade g_trade;

bool IsPayloadTrimCharacter(const ushort character)
{
   return character == ' ' || character == '\t' || character == '\r' ||
          character == '\n' || character == 0 || character == 0xFEFF;
}

string TrimPackagePayload(string payload)
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

bool DecodePackagePayload(const uchar &bytes[], string &payload)
{
   int length = ArraySize(bytes);
   if(length >= 3 && bytes[0] == 0xEF && bytes[1] == 0xBB && bytes[2] == 0xBF)
      return DecodeUtf8(bytes, 3, payload);
   if(length >= 2 && bytes[0] == 0xFF && bytes[1] == 0xFE)
      return DecodeUtf16(bytes, 2, true, payload);
   if(length >= 2 && bytes[0] == 0xFE && bytes[1] == 0xFF)
      return DecodeUtf16(bytes, 2, false, payload);

   // execution_package.json is UTF-8 when no byte-order mark is present.
   return DecodeUtf8(bytes, 0, payload);
}

bool ReadExecutionPackage(string &payload)
{
   ResetLastError();
   int handle = FileOpen(
      "RP_AI_EA\\shared\\XAUUSD\\execution_package.json",
      FILE_READ | FILE_BIN | FILE_COMMON | FILE_SHARE_READ | FILE_SHARE_WRITE
   );
   if(handle == INVALID_HANDLE)
   {
      Print("PACKAGE_FILE_OPEN_FAIL | error=", GetLastError(), " | path=", EXECUTION_PACKAGE_PATH);
      return false;
   }

   long file_size = FileSize(handle);
   if(file_size <= 0 || file_size > 1048576)
   {
      FileClose(handle);
      Print(file_size == 0 ? "PACKAGE_FILE_EMPTY" : "PACKAGE_FILE_SIZE_INVALID");
      return false;
   }

   uchar bytes[];
   int bytes_read = FileReadArray(handle, bytes, 0, (int)file_size);
   FileClose(handle);
   if(bytes_read != (int)file_size || !DecodePackagePayload(bytes, payload))
   {
      Print("PACKAGE_PAYLOAD_DECODE_FAIL | bytes_read=", bytes_read, " | file_size=", file_size);
      return false;
   }

   payload = TrimPackagePayload(payload);
   if(payload == "") { Print("PACKAGE_FILE_EMPTY"); return false; }
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


#define EXECUTOR_STATE_PATH "RP_AI_EA\\shared\\XAUUSD\\executor_state.json"
#define EXECUTOR_ACCEPTED_UUIDS_PATH "RP_AI_EA\\shared\\XAUUSD\\executor_accepted_uuids.log"
#define EXECUTION_RESULT_PATH "RP_AI_EA\\shared\\XAUUSD\\execution_result.json"
#define EXECUTOR_TRACE_PATH "RP_AI_EA\\shared\\XAUUSD\\executor_trace.log"
#define PACKAGE_SCHEMA_VERSION "1.0"
#define PACKAGE_PRODUCER "RP_AI_RUNTIME"
#define PACKAGE_PRODUCER_VERSION "27.5"
#define MAX_HEARTBEAT_AGE_SECONDS 30

string JsonEscape(string value)
{
   StringReplace(value, "\\", "\\\\");
   StringReplace(value, "\"", "\\\"");
   StringReplace(value, "\r", "\\r");
   StringReplace(value, "\n", "\\n");
   return value;
}

string UtcTimestamp()
{
   MqlDateTime value; TimeToStruct(TimeGMT(), value);
   return StringFormat("%04d-%02d-%02dT%02d:%02d:%02dZ", value.year, value.mon,
                       value.day, value.hour, value.min, value.sec);
}

void Trace(const string stage, const string status, const string execution_uuid,
           const string owner, const string reason)
{
   int handle=FileOpen(EXECUTOR_TRACE_PATH, FILE_READ|FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_COMMON|FILE_SHARE_READ);
   if(handle==INVALID_HANDLE) { Print("EXECUTOR_TRACE_OPEN_FAILED | error=", GetLastError()); return; }
   FileSeek(handle, 0, SEEK_END);
   string record=StringFormat("{\"timestamp\":\"%s\",\"stage\":\"%s\",\"status\":\"%s\",\"execution_uuid\":\"%s\",\"failure_owner\":\"%s\",\"failure_reason\":\"%s\"}",
      UtcTimestamp(),JsonEscape(stage),JsonEscape(status),JsonEscape(execution_uuid),JsonEscape(owner),JsonEscape(reason));
   FileWriteString(handle, record+"\r\n"); FileFlush(handle); FileClose(handle);
}

bool IsCanonicalUuid(const string value)
{
   if(StringLen(value)!=36 || StringGetCharacter(value,8)!='-' || StringGetCharacter(value,13)!='-' ||
      StringGetCharacter(value,18)!='-' || StringGetCharacter(value,23)!='-') return false;
   for(int i=0;i<36;i++)
   {
      if(i==8 || i==13 || i==18 || i==23) continue;
      ushort c=StringGetCharacter(value,i);
      if(!((c>='0' && c<='9') || (c>='a' && c<='f'))) return false;
   }
   return true;
}

bool ReadStateUuid(string &last_uuid)
{
   last_uuid="";
   int handle=FileOpen(EXECUTOR_STATE_PATH,FILE_READ|FILE_TXT|FILE_ANSI|FILE_COMMON|FILE_SHARE_READ);
   if(handle==INVALID_HANDLE) return GetLastError()==5004; // no state is valid only before first acceptance
   string json=FileReadString(handle); FileClose(handle);
   if(!ReadFieldString(json,"last_accepted_execution_uuid",last_uuid) || !IsCanonicalUuid(last_uuid)) return false;
   return true;
}

bool WasExecutionUuidAccepted(const string execution_uuid, bool &state_readable)
{
   state_readable=true;
   int handle=FileOpen(EXECUTOR_ACCEPTED_UUIDS_PATH,FILE_READ|FILE_TXT|FILE_ANSI|FILE_COMMON|FILE_SHARE_READ);
   if(handle==INVALID_HANDLE)
   {
      if(GetLastError()==5004) return false;
      state_readable=false; return false;
   }
   while(!FileIsEnding(handle))
   {
      string accepted=FileReadString(handle);
      if(accepted==execution_uuid) { FileClose(handle); return true; }
      if(accepted!="" && !IsCanonicalUuid(accepted)) { FileClose(handle); state_readable=false; return false; }
   }
   FileClose(handle); return false;
}

bool AppendAcceptedUuid(const string execution_uuid)
{
   int handle=FileOpen(EXECUTOR_ACCEPTED_UUIDS_PATH,FILE_READ|FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_COMMON|FILE_SHARE_READ);
   if(handle==INVALID_HANDLE) return false;
   FileSeek(handle,0,SEEK_END);
   bool okay=FileWriteString(handle,execution_uuid+"\r\n")==StringLen(execution_uuid)+2;
   FileFlush(handle); FileClose(handle); return okay;
}

bool PersistAcceptedUuid(const string execution_uuid, const long market_sequence)
{
   int handle=FileOpen(EXECUTOR_STATE_PATH,FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_COMMON);
   if(handle==INVALID_HANDLE) return false;
   string value=StringFormat("{\"schema_version\":\"1.0\",\"last_accepted_execution_uuid\":\"%s\",\"last_market_sequence\":%I64d,\"accepted_at\":\"%s\"}\r\n",
                             execution_uuid,market_sequence,UtcTimestamp());
   bool okay=FileWriteString(handle,value)==StringLen(value); FileFlush(handle); FileClose(handle);
   return okay;
}

void PersistResult(const string execution_uuid,const ulong ticket,const uint retcode,const string status)
{
   int handle=FileOpen(EXECUTION_RESULT_PATH,FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_COMMON);
   if(handle==INVALID_HANDLE) { Trace("Execution result","FAILED",execution_uuid,"POSITION","RESULT_PERSIST_FAILED"); return; }
   string value=StringFormat("{\"execution_uuid\":\"%s\",\"ticket\":%I64u,\"retcode\":%u,\"broker_time\":\"%s\",\"execution_status\":\"%s\"}\r\n",
                             execution_uuid,ticket,retcode,UtcTimestamp(),status);
   FileWriteString(handle,value); FileFlush(handle); FileClose(handle);
   Trace("Execution result","RECORDED",execution_uuid,"NONE",status);
}

bool ValidVolume(const string symbol,const double volume,string &reason)
{
   double minimum=SymbolInfoDouble(symbol,SYMBOL_VOLUME_MIN);
   double maximum=SymbolInfoDouble(symbol,SYMBOL_VOLUME_MAX);
   double step=SymbolInfoDouble(symbol,SYMBOL_VOLUME_STEP);
   if(!MathIsValidNumber(volume) || volume<minimum || volume>maximum || step<=0.0)
      { reason="VOLUME_INVALID"; return false; }
   if(MathAbs(volume/step-MathRound(volume/step))>0.0000001)
      { reason="VOLUME_STEP_INVALID"; return false; }
   return true;
}

bool BrokerValidation(const string symbol,const string direction,const double volume,
                      const double sl,const double tp,MqlTradeRequest &request,string &reason)
{
   if(symbol=="" || !SymbolSelect(symbol,true)) { reason="SYMBOL_UNAVAILABLE"; return false; }
   long trade_mode=SymbolInfoInteger(symbol,SYMBOL_TRADE_MODE);
   if(!TerminalInfoInteger(TERMINAL_CONNECTED) || !TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) ||
      !MQLInfoInteger(MQL_TRADE_ALLOWED) || trade_mode==SYMBOL_TRADE_MODE_DISABLED)
      { reason="TRADING_DISABLED"; return false; }
   MqlTick tick;
   if(!SymbolInfoTick(symbol,tick) || tick.time<=0 || (TimeCurrent()-tick.time)>60)
      { reason="MARKET_CLOSED"; return false; }
   if(!ValidVolume(symbol,volume,reason)) return false;
   ENUM_ORDER_TYPE order_type=direction=="BUY" ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   double price=direction=="BUY" ? tick.ask : tick.bid;
   double margin=0.0;
   if(!OrderCalcMargin(order_type,symbol,volume,price,margin) || margin<=0.0 ||
      AccountInfoDouble(ACCOUNT_MARGIN_FREE)<margin) { reason="MARGIN_INSUFFICIENT"; return false; }
   double point=SymbolInfoDouble(symbol,SYMBOL_POINT);
   double minimum_stop=(double)SymbolInfoInteger(symbol,SYMBOL_TRADE_STOPS_LEVEL)*point;
   if((sl>0.0 && ((direction=="BUY" && (sl>=price || price-sl<minimum_stop)) ||
                  (direction=="SELL" && (sl<=price || sl-price<minimum_stop)))) ||
      (tp>0.0 && ((direction=="BUY" && (tp<=price || tp-price<minimum_stop)) ||
                  (direction=="SELL" && (tp>=price || price-tp<minimum_stop)))))
      { reason="STOP_LEVELS_INVALID"; return false; }
   ZeroMemory(request); request.action=TRADE_ACTION_DEAL; request.magic=InpMagic;
   request.symbol=symbol; request.volume=volume; request.type=order_type; request.price=price;
   request.sl=sl; request.tp=tp; request.type_filling=(ENUM_ORDER_TYPE_FILLING)SymbolInfoInteger(symbol,SYMBOL_FILLING_MODE);
   request.comment="RP_GOVERNED";
   return true;
}

bool ValidatePackage(const string json,string &execution_uuid,string &decision_uuid,string &symbol,
                     string &direction,double &volume,double &sl,double &tp,long &market_sequence,string &reason)
{
   string producer,producer_version,schema_version,source_uuid,execution_timestamp;
   double heartbeat=0.0,sequence=0.0;
   if(!ReadFieldString(json,"execution_uuid",execution_uuid) || !IsCanonicalUuid(execution_uuid)) { reason="INVALID_EXECUTION_UUID"; return false; }
   if(!ReadFieldString(json,"decision_uuid",decision_uuid) || !IsCanonicalUuid(decision_uuid)) { reason="INVALID_DECISION_UUID"; return false; }
   if(!ReadFieldString(json,"producer",producer) || producer!=PACKAGE_PRODUCER) { reason="INVALID_PRODUCER"; return false; }
   if(!ReadFieldString(json,"producer_version",producer_version) || producer_version!=PACKAGE_PRODUCER_VERSION) { reason="INVALID_PRODUCER_VERSION"; return false; }
   if(!ReadFieldString(json,"schema_version",schema_version) || schema_version!=PACKAGE_SCHEMA_VERSION) { reason="INVALID_SCHEMA_VERSION"; return false; }
   if(!ReadFieldString(json,"source_uuid",source_uuid) || !IsCanonicalUuid(source_uuid)) { reason="INVALID_SOURCE_UUID"; return false; }
   if(!ReadFieldNumber(json,"heartbeat_unix",heartbeat) || heartbeat<=0 || MathAbs((double)TimeGMT()-heartbeat)>MAX_HEARTBEAT_AGE_SECONDS)
      { reason="STALE_HEARTBEAT"; return false; }
   if(!ReadFieldNumber(json,"market_sequence",sequence) || sequence<1 || sequence!=MathFloor(sequence)) { reason="INVALID_MARKET_SEQUENCE"; return false; }
   market_sequence=(long)sequence;
   // The canonical assembler publishes a package only after independently checking
   // executable runtime state, entry permission, and OrderSend permission.  Exact
   // producer/version/schema validation above verifies that capability boundary;
   // direction alone is never treated as authority.
   if(!ReadFieldString(json,"execution_timestamp",execution_timestamp) || execution_timestamp=="") { reason="RUNTIME_EXECUTION_STATE_UNVERIFIED"; return false; }
   if(!ReadFieldString(json,"symbol",symbol) || symbol=="") { reason="ENTRY_PERMISSION_UNVERIFIED"; return false; }
   if(!ReadFieldString(json,"direction",direction) || (direction!="BUY" && direction!="SELL")) { reason="ORDERSEND_PERMISSION_UNVERIFIED"; return false; }
   if(!ReadFieldNumber(json,"lot_size",volume) || !ReadFieldNumber(json,"sl",sl) || !ReadFieldNumber(json,"tp",tp)) { reason="INVALID_ORDER_FIELDS"; return false; }
   return MathIsValidNumber(volume) && MathIsValidNumber(sl) && MathIsValidNumber(tp);
}

void Reject(const string stage,const string execution_uuid,const string owner,const string reason)
{
   Trace(stage,"REJECTED",execution_uuid,owner,reason);
   PrintFormat("EXECUTOR_REJECTED | owner=%s | reason=%s | execution_uuid=%s",owner,reason,execution_uuid);
}

void OnTick()
{
   if(InpEmergencyDisable) { Reject("Validation","","VALIDATION","EMERGENCY_DISABLE_ACTIVE"); return; }
   string json;
   if(!ReadExecutionPackage(json)) return;
   string execution_uuid="",decision_uuid="",symbol="",direction="",reason="";
   double volume=0.0,sl=0.0,tp=0.0; long market_sequence=0;
   if(!ValidatePackage(json,execution_uuid,decision_uuid,symbol,direction,volume,sl,tp,market_sequence,reason))
      { Reject("Validation",execution_uuid,"PACKAGE",reason); return; }
   Trace("Validation","PASSED",execution_uuid,"NONE","fully authorized canonical package");

   string last_uuid;
   if(!ReadStateUuid(last_uuid)) { Reject("Validation",execution_uuid,"VALIDATION","EXECUTOR_STATE_INVALID"); return; }
   bool ledger_readable=true;
   bool duplicate=WasExecutionUuidAccepted(execution_uuid,ledger_readable);
   if(!ledger_readable) { Reject("Validation",execution_uuid,"VALIDATION","EXECUTOR_UUID_LEDGER_INVALID"); return; }
   if(last_uuid==execution_uuid || duplicate) { Reject("Validation",execution_uuid,"VALIDATION","DUPLICATE_EXECUTION_UUID"); return; }

   MqlTradeRequest request; MqlTradeResult result;
   if(!BrokerValidation(symbol,direction,volume,sl,tp,request,reason))
      { Reject("Broker validation",execution_uuid,"BROKER",reason); return; }
   Trace("Broker validation","PASSED",execution_uuid,"NONE","symbol trading market volume margin stops valid");

   // Persist acceptance before broker submission: a crash may suppress an order,
   // but can never submit the same execution_uuid twice after restart or deletion.
   if(!AppendAcceptedUuid(execution_uuid) || !PersistAcceptedUuid(execution_uuid,market_sequence))
      { Reject("Package accepted",execution_uuid,"VALIDATION","EXECUTOR_STATE_PERSIST_FAILED"); return; }
   Trace("Package accepted","ACCEPTED",execution_uuid,"NONE","immutable duplicate authority persisted");
   ZeroMemory(result);
   Trace("OrderSend","ATTEMPTED",execution_uuid,"NONE","broker request submitted");
   ResetLastError();
   bool sent=OrderSend(request,result);
   string status=sent && (result.retcode==TRADE_RETCODE_DONE || result.retcode==TRADE_RETCODE_PLACED || result.retcode==TRADE_RETCODE_DONE_PARTIAL)
                 ? "POSITION_LIFECYCLE_INITIATED" : "ORDER_REJECTED";
   PersistResult(execution_uuid,result.order,result.retcode,status);
   if(status=="POSITION_LIFECYCLE_INITIATED")
      Trace("OrderSend","SUCCEEDED",execution_uuid,"NONE","position lifecycle initiated");
   else
      Reject("OrderSend",execution_uuid,"ORDERSEND",StringFormat("RETCODE_%u_ERROR_%d",result.retcode,GetLastError()));
}
