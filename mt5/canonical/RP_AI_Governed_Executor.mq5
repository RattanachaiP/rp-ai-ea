//+------------------------------------------------------------------+
//| RP Governed Executor -- canonical package consumer               |
//+------------------------------------------------------------------+
#property strict
#property version   "28.05"
#property description "Canonical governed one-shot execution_package.json consumer."

#include "RP_ExecutionPackageContract.mqh"

#define EXECUTION_PACKAGE_PATH "RP_AI_EA\\shared\\XAUUSD\\execution_package.json"

input bool   InpEmergencyDisable          = false;
input ulong  InpMagic                     = 2800001;


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
   uint bytes_read = FileReadArray(handle, bytes, 0, (int)file_size);
   FileClose(handle);
   if((long)bytes_read != file_size || !DecodePackagePayload(bytes, payload))
   {
      PrintFormat("PACKAGE_PAYLOAD_DECODE_FAIL | bytes_read=%u | file_size=%I64d",bytes_read,file_size);
      return false;
   }

   payload = TrimPackagePayload(payload);
   if(payload == "") { Print("PACKAGE_FILE_EMPTY"); return false; }
   return true;
}

bool IsJsonWhitespace(const ushort c) { return c==' ' || c=='\\t' || c=='\\r' || c=='\\n'; }
void SkipWhitespace(const string json,int &cursor) { while(cursor<StringLen(json) && IsJsonWhitespace(StringGetCharacter(json,cursor))) cursor++; }
int HexDigit(const ushort c)
{
   if(c>='0' && c<='9') return (int)(c-'0');
   if(c>='a' && c<='f') return (int)(c-'a'+10);
   if(c>='A' && c<='F') return (int)(c-'A'+10);
   return -1;
}
bool ParseHexUnit(const string json,int &cursor,ushort &unit)
{
   if(cursor+4>StringLen(json)) return false;
   uint value=0;
   for(int i=0;i<4;i++) { int digit=HexDigit(StringGetCharacter(json,cursor++)); if(digit<0) return false; value=(value<<4)+(uint)digit; }
   unit=(ushort)value; return true;
}
bool ParseJsonString(const string json,int &cursor,string &value)
{
   value="";
   if(cursor>=StringLen(json) || StringGetCharacter(json,cursor++)!='"') return false;
   while(cursor<StringLen(json))
   {
      ushort c=StringGetCharacter(json,cursor++);
      if(c=='"') return true;
      if(c<0x20) return false;
      if(c!='\\') { value+=CharToString(c); continue; }
      if(cursor>=StringLen(json)) return false;
      ushort escape=StringGetCharacter(json,cursor++);
      if(escape=='"' || escape=='\\' || escape=='/') value+=CharToString(escape);
      else if(escape=='b') value+=CharToString(8);
      else if(escape=='f') value+=CharToString(12);
      else if(escape=='n') value+="\n";
      else if(escape=='r') value+="\r";
      else if(escape=='t') value+="\t";
      else if(escape=='u')
      {
         ushort high=0; if(!ParseHexUnit(json,cursor,high)) return false;
         if(high>=0xD800 && high<=0xDBFF)
         {
            if(cursor+2>StringLen(json) || StringGetCharacter(json,cursor++)!='\\' || StringGetCharacter(json,cursor++)!='u') return false;
            ushort low=0; if(!ParseHexUnit(json,cursor,low) || low<0xDC00 || low>0xDFFF) return false;
            value+=CharToString(high)+CharToString(low);
         }
         else if(high>=0xDC00 && high<=0xDFFF) return false;
         else value+=CharToString(high);
      }
      else return false;
   }
   return false;
}
bool ParseJsonNumber(const string json,int &cursor,string &token,const bool integer_required)
{
   int start=cursor,length=StringLen(json);
   if(cursor<length && StringGetCharacter(json,cursor)=='-') cursor++;
   if(cursor>=length) return false;
   ushort c=StringGetCharacter(json,cursor);
   if(c=='0') { cursor++; if(cursor<length && StringGetCharacter(json,cursor)>='0' && StringGetCharacter(json,cursor)<='9') return false; }
   else if(c>='1' && c<='9') { do { cursor++; } while(cursor<length && StringGetCharacter(json,cursor)>='0' && StringGetCharacter(json,cursor)<='9'); }
   else return false;
   if(cursor<length && StringGetCharacter(json,cursor)=='.')
   {
      if(integer_required) return false; cursor++;
      if(cursor>=length || StringGetCharacter(json,cursor)<'0' || StringGetCharacter(json,cursor)>'9') return false;
      while(cursor<length && StringGetCharacter(json,cursor)>='0' && StringGetCharacter(json,cursor)<='9') cursor++;
   }
   if(cursor<length && (StringGetCharacter(json,cursor)=='e' || StringGetCharacter(json,cursor)=='E'))
   {
      if(integer_required) return false; cursor++;
      if(cursor<length && (StringGetCharacter(json,cursor)=='+' || StringGetCharacter(json,cursor)=='-')) cursor++;
      if(cursor>=length || StringGetCharacter(json,cursor)<'0' || StringGetCharacter(json,cursor)>'9') return false;
      while(cursor<length && StringGetCharacter(json,cursor)>='0' && StringGetCharacter(json,cursor)<='9') cursor++;
   }
   token=StringSubstr(json,start,cursor-start);
   double numeric=StringToDouble(token);
   return MathIsValidNumber(numeric);
}
int ContractFieldIndex(const string key,const string &names[])
{
   for(int i=0;i<ArraySize(names);i++) if(names[i]==key) return i;
   return -1;
}
bool ParseCanonicalPackage(const string json,string &values[],string &reason)
{
   string names[]; RPJsonFieldType types[]; RPInitializePackageContract(names,types);
   ArrayResize(values,RP_EXECUTION_PACKAGE_FIELD_COUNT); bool seen[]; ArrayResize(seen,RP_EXECUTION_PACKAGE_FIELD_COUNT); ArrayInitialize(seen,false);
   int cursor=0,count=0; SkipWhitespace(json,cursor);
   if(cursor>=StringLen(json) || StringGetCharacter(json,cursor++)!='{') { reason="ROOT_OBJECT_REQUIRED"; return false; }
   SkipWhitespace(json,cursor);
   if(cursor<StringLen(json) && StringGetCharacter(json,cursor)=='}') { reason="MISSING_FIELD"; return false; }
   while(cursor<StringLen(json))
   {
      string key,value; if(!ParseJsonString(json,cursor,key)) { reason="INVALID_JSON_KEY"; return false; }
      int index=ContractFieldIndex(key,names); if(index<0) { reason="UNKNOWN_FIELD"; return false; }
      if(index!=count) { reason="NON_CANONICAL_FIELD_ORDER"; return false; }
      if(seen[index]) { reason="DUPLICATE_FIELD"; return false; }
      SkipWhitespace(json,cursor); if(cursor>=StringLen(json) || StringGetCharacter(json,cursor++)!=':') { reason="MISSING_COLON"; return false; }
      SkipWhitespace(json,cursor);
      if(types[index]==RP_JSON_STRING) { if(!ParseJsonString(json,cursor,value)) { reason="WRONG_FIELD_TYPE"; return false; } }
      else if(!ParseJsonNumber(json,cursor,value,types[index]==RP_JSON_INTEGER)) { reason="INVALID_NUMBER_OR_TYPE"; return false; }
      values[index]=value; seen[index]=true; count++;
      SkipWhitespace(json,cursor); if(cursor>=StringLen(json)) { reason="UNTERMINATED_OBJECT"; return false; }
      ushort delimiter=StringGetCharacter(json,cursor++);
      if(delimiter=='}') break;
      if(delimiter!=',') { reason="INVALID_DELIMITER"; return false; }
      SkipWhitespace(json,cursor);
   }
   SkipWhitespace(json,cursor);
   if(cursor!=StringLen(json)) { reason="TRAILING_CONTENT"; return false; }
   if(count!=RP_EXECUTION_PACKAGE_FIELD_COUNT) { reason="MISSING_FIELD"; return false; }
   return true;
}

#define EXECUTOR_STATE_PATH "RP_AI_EA\\shared\\XAUUSD\\executor_state.json"
#define EXECUTOR_JOURNAL_PATH "RP_AI_EA\\shared\\XAUUSD\\executor_journal.log"
#define EXECUTION_RESULT_PATH "RP_AI_EA\\shared\\XAUUSD\\execution_result.json"
#define EXECUTOR_TRACE_PATH "RP_AI_EA\\shared\\XAUUSD\\executor_trace.log"
// MQL5 runtime error 5004 is returned when FileOpen cannot open a file.  MQL5
// does not provide ERR_FILE_NOT_FOUND as a built-in identifier.
#define RP_ERR_FILE_CANNOT_OPEN 5004

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

string BrokerTimestamp()
{
   MqlDateTime value; TimeToStruct(TimeTradeServer(),value);
   return StringFormat("%04d-%02d-%02dT%02d:%02d:%02dZ",value.year,value.mon,
                       value.day,value.hour,value.min,value.sec);
}

void Trace(const string stage, const string status, const string execution_uuid,
           const string owner, const string reason)
{
   int handle=FileOpen(EXECUTOR_TRACE_PATH, FILE_READ|FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_COMMON|FILE_SHARE_READ);
   if(handle==INVALID_HANDLE) { Print("EXECUTOR_TRACE_OPEN_FAILED | error=", GetLastError()); return; }
   FileSeek(handle, 0, SEEK_END);
   string record=StringFormat("{\"timestamp\":\"%s\",\"stage\":\"%s\",\"status\":\"%s\",\"execution_uuid\":\"%s\",\"failure_owner\":\"%s\",\"failure_reason\":\"%s\"}",
      UtcTimestamp(),JsonEscape(stage),JsonEscape(status),JsonEscape(execution_uuid),JsonEscape(owner),JsonEscape(reason));
   string line=record+"\r\n";
   FileWriteString(handle,line); FileFlush(handle); FileClose(handle);
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

bool ParseExecutorState(const string json,long &sequence,string &execution_uuid,string &decision_uuid,string &status)
{
   string expected[]={"schema_version","last_market_sequence","last_execution_uuid","last_decision_uuid","last_execution_status","updated_at"};
   bool seen[]; ArrayResize(seen,6); ArrayInitialize(seen,false); int cursor=0,count=0; string schema,updated;
   SkipWhitespace(json,cursor); if(cursor>=StringLen(json) || StringGetCharacter(json,cursor++)!='{') return false;
   while(cursor<StringLen(json))
   {
      SkipWhitespace(json,cursor); string key,value; if(!ParseJsonString(json,cursor,key)) return false;
      int index=-1; for(int i=0;i<6;i++) if(expected[i]==key) index=i;
      if(index<0 || seen[index]) return false;
      SkipWhitespace(json,cursor); if(cursor>=StringLen(json) || StringGetCharacter(json,cursor++)!=':') return false; SkipWhitespace(json,cursor);
      if(index==1) { if(!ParseJsonNumber(json,cursor,value,true)) return false; sequence=(long)StringToInteger(value); }
      else if(!ParseJsonString(json,cursor,value)) return false;
      if(index==0) schema=value; else if(index==2) execution_uuid=value; else if(index==3) decision_uuid=value; else if(index==4) status=value; else if(index==5) updated=value;
      seen[index]=true; count++; SkipWhitespace(json,cursor); if(cursor>=StringLen(json)) return false;
      ushort delimiter=StringGetCharacter(json,cursor++); if(delimiter=='}') break; if(delimiter!=',') return false;
   }
   SkipWhitespace(json,cursor);
   return cursor==StringLen(json) && count==6 && schema=="1.0" && sequence>0 &&
          IsCanonicalUuid(execution_uuid) && IsCanonicalUuid(decision_uuid) && updated!="";
}

bool LoadExecutorState(bool &exists,long &sequence,string &execution_uuid,string &decision_uuid,string &status)
{
   exists=false; ResetLastError();
   int handle=FileOpen(EXECUTOR_STATE_PATH,FILE_READ|FILE_TXT|FILE_ANSI|FILE_COMMON|FILE_SHARE_READ);
   if(handle==INVALID_HANDLE) return GetLastError()==RP_ERR_FILE_CANNOT_OPEN;
   exists=true; string json=""; while(!FileIsEnding(handle)) json+=FileReadString(handle); FileClose(handle);
   return ParseExecutorState(json,sequence,execution_uuid,decision_uuid,status);
}

bool AppendJournal(const string status,const string execution_uuid,const string decision_uuid,const long sequence,const string reason)
{
   int handle=FileOpen(EXECUTOR_JOURNAL_PATH,FILE_READ|FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_COMMON|FILE_SHARE_READ);
   if(handle==INVALID_HANDLE) return false;
   FileSeek(handle,0,SEEK_END);
   string line=StringFormat("%I64d\t%s\t%s\t%s\t%s\t%s\r\n",sequence,execution_uuid,decision_uuid,status,UtcTimestamp(),reason);
   bool okay=FileWriteString(handle,line)==(uint)StringLen(line); FileFlush(handle); FileClose(handle); return okay;
}

bool InspectJournal(const string candidate_uuid,bool &duplicate,long &maximum_sequence,string &last_status)
{
   duplicate=false; maximum_sequence=0; last_status=""; ResetLastError();
   int handle=FileOpen(EXECUTOR_JOURNAL_PATH,FILE_READ|FILE_TXT|FILE_ANSI|FILE_COMMON|FILE_SHARE_READ);
   if(handle==INVALID_HANDLE) return GetLastError()==RP_ERR_FILE_CANNOT_OPEN;
   while(!FileIsEnding(handle))
   {
      string line=FileReadString(handle); if(line=="") continue;
      string parts[]; if(StringSplit(line,'\t',parts)!=6) { FileClose(handle); return false; }
      long sequence=(long)StringToInteger(parts[0]);
      if(sequence<1 || !IsCanonicalUuid(parts[1]) || !IsCanonicalUuid(parts[2])) { FileClose(handle); return false; }
      if(sequence>maximum_sequence) maximum_sequence=sequence;
      if(parts[1]==candidate_uuid) { duplicate=true; last_status=parts[3]; }
   }
   FileClose(handle); return true;
}

bool ReplaceTextFailClosed(const string path,const string value,const string publication_id)
{
   // The already validated execution UUID plus transition name makes this
   // publication-specific and collision-resistant without creating another
   // authority or a random identity inside the Executor.
   string temporary=path+"."+publication_id+".tmp";
   if(FileIsExist(temporary,FILE_COMMON))
   {
      // A stale file is never reused or overwritten.  Cleanup is explicit and
      // this publication still fails closed; a later tick may try a new flow.
      FileDelete(temporary,FILE_COMMON);
      return false;
   }
   int handle=FileOpen(temporary,FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_COMMON);
   if(handle==INVALID_HANDLE) return false;
   bool okay=FileWriteString(handle,value)==(uint)StringLen(value);
   FileFlush(handle); FileClose(handle);
   if(!okay) { FileDelete(temporary,FILE_COMMON); return false; }
   // Source and destination are in the same Common/Files directory. FileMove
   // provides the platform's best-effort replacement semantics; failures are
   // reported and the existing destination is never deliberately deleted.
   if(!FileMove(temporary,FILE_COMMON,path,FILE_COMMON|FILE_REWRITE))
   {
      FileDelete(temporary,FILE_COMMON);
      return false;
   }
   return true;
}

bool PersistExecutorState(const string execution_uuid,const string decision_uuid,const long market_sequence,const string status)
{
   string value=StringFormat("{\"schema_version\":\"1.0\",\"last_market_sequence\":%I64d,\"last_execution_uuid\":\"%s\",\"last_decision_uuid\":\"%s\",\"last_execution_status\":\"%s\",\"updated_at\":\"%s\"}",
      market_sequence,execution_uuid,decision_uuid,status,UtcTimestamp());
   return ReplaceTextFailClosed(EXECUTOR_STATE_PATH,value,execution_uuid+"."+status);
}

bool PersistTransition(const string status,const string execution_uuid,const string decision_uuid,const long sequence,const string reason)
{
   return AppendJournal(status,execution_uuid,decision_uuid,sequence,reason) &&
          PersistExecutorState(execution_uuid,decision_uuid,sequence,status);
}

bool PersistResult(const string execution_uuid,const ulong ticket,const uint retcode,const string status)
{
   string value=StringFormat("{\"execution_uuid\":\"%s\",\"ticket\":%I64u,\"retcode\":%u,\"broker_time\":\"%s\",\"execution_status\":\"%s\"}\r\n",
                             execution_uuid,ticket,retcode,BrokerTimestamp(),status);
   if(!ReplaceTextFailClosed(EXECUTION_RESULT_PATH,value,execution_uuid+".result"))
      { Trace("Execution result","FAILED",execution_uuid,"POSITION","RESULT_PERSIST_FAILED"); return false; }
   Trace("Execution result","RECORDED",execution_uuid,"NONE",status);
   return true;
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
   string values[];
   if(!ParseCanonicalPackage(json,values,reason)) return false;
   execution_uuid=values[0]; decision_uuid=values[1]; market_sequence=(long)StringToInteger(values[2]);
   long heartbeat=(long)StringToInteger(values[3]); symbol=values[8]; direction=values[9];
   volume=StringToDouble(values[12]); sl=StringToDouble(values[14]); tp=StringToDouble(values[15]);
   if(!IsCanonicalUuid(execution_uuid)) { reason="INVALID_EXECUTION_UUID"; return false; }
   if(!IsCanonicalUuid(decision_uuid)) { reason="INVALID_DECISION_UUID"; return false; }
   if(values[4]!=RP_PACKAGE_PRODUCER) { reason="INVALID_PRODUCER"; return false; }
   if(values[5]!=RP_PACKAGE_PRODUCER_VERSION) { reason="INVALID_PRODUCER_VERSION"; return false; }
   if(values[6]!=RP_PACKAGE_SCHEMA_VERSION) { reason="INVALID_SCHEMA_VERSION"; return false; }
   if(!IsCanonicalUuid(values[7])) { reason="INVALID_SOURCE_UUID"; return false; }
   if(heartbeat<=0 || MathAbs((double)((long)TimeGMT()-heartbeat))>(double)RP_EXECUTOR_PACKAGE_MAX_AGE_SECONDS) { reason="STALE_PACKAGE"; return false; }
   if(market_sequence<1) { reason="INVALID_MARKET_SEQUENCE"; return false; }
   if(symbol=="") { reason="ENTRY_PERMISSION_UNVERIFIED"; return false; }
   if(direction!="BUY" && direction!="SELL") { reason="ORDERSEND_PERMISSION_UNVERIFIED"; return false; }
   if(!MathIsValidNumber(volume) || !MathIsValidNumber(sl) || !MathIsValidNumber(tp)) { reason="INVALID_ORDER_FIELDS"; return false; }
   return true;
}

void Reject(const string stage,const string execution_uuid,const string owner,const string reason)
{
   Trace(stage,"REJECTED",execution_uuid,owner,reason);
   PrintFormat("EXECUTOR_REJECTED | owner=%s | reason=%s | execution_uuid=%s",owner,reason,execution_uuid);
}

void OnTick()
{
   if(InpEmergencyDisable) { Reject("Validation","","VALIDATION","EMERGENCY_DISABLE_ACTIVE"); return; }
   string json; if(!ReadExecutionPackage(json)) return;
   string execution_uuid="",decision_uuid="",symbol="",direction="",reason="";
   double volume=0.0,sl=0.0,tp=0.0; long market_sequence=0;
   if(!ValidatePackage(json,execution_uuid,decision_uuid,symbol,direction,volume,sl,tp,market_sequence,reason))
      { Reject("Validation",execution_uuid,"PACKAGE",reason); return; }
   Trace("Validation","PASSED",execution_uuid,"NONE","exact canonical package accepted for broker validation");

   bool state_exists=false; long state_sequence=0; string state_uuid,state_decision,state_status;
   if(!LoadExecutorState(state_exists,state_sequence,state_uuid,state_decision,state_status))
      { Reject("Validation",execution_uuid,"VALIDATION","EXECUTOR_STATE_CORRUPT_OR_INACCESSIBLE"); return; }
   bool duplicate=false; long journal_sequence=0; string journal_status;
   if(!InspectJournal(execution_uuid,duplicate,journal_sequence,journal_status))
      { Reject("Validation",execution_uuid,"VALIDATION","EXECUTOR_JOURNAL_CORRUPT_OR_INACCESSIBLE"); return; }
   if(duplicate)
   {
      if(journal_status=="SUBMITTING") AppendJournal("UNKNOWN_OUTCOME",execution_uuid,decision_uuid,market_sequence,"RECOVERED_UNCERTAIN_SUBMISSION");
      Reject("Validation",execution_uuid,"VALIDATION",journal_status=="SUBMITTING" ? "UNKNOWN_OUTCOME" : "DUPLICATE_EXECUTION_UUID"); return;
   }
   long authority_sequence=state_sequence>journal_sequence ? state_sequence : journal_sequence;
   if(market_sequence<=authority_sequence) { Reject("Validation",execution_uuid,"VALIDATION","NON_MONOTONIC_MARKET_SEQUENCE"); return; }

   MqlTradeRequest request; MqlTradeResult result;
   if(!BrokerValidation(symbol,direction,volume,sl,tp,request,reason))
      { Reject("Broker validation",execution_uuid,"BROKER",reason); return; }
   Trace("Broker validation","PASSED",execution_uuid,"NONE","symbol trading market volume margin stops valid");

   if(!PersistTransition("ACCEPTED",execution_uuid,decision_uuid,market_sequence,"PACKAGE_ACCEPTED"))
      { Reject("Package accepted",execution_uuid,"VALIDATION","ACCEPTANCE_PERSIST_FAILED"); return; }
   Trace("Package accepted","ACCEPTED",execution_uuid,"NONE","authoritative journal and monotonic state persisted");
   if(!PersistTransition("SUBMITTING",execution_uuid,decision_uuid,market_sequence,"ORDERSEND_IMMINENT"))
      { PersistTransition("UNKNOWN_OUTCOME",execution_uuid,decision_uuid,market_sequence,"SUBMITTING_PERSIST_FAILED"); Reject("OrderSend",execution_uuid,"ORDERSEND","SUBMITTING_PERSIST_FAILED"); return; }

   ZeroMemory(result); Trace("OrderSend","ATTEMPTED",execution_uuid,"NONE","broker request submitted"); ResetLastError();
   bool api_result=OrderSend(request,result);
   string journal_terminal,result_status;
   if(result.retcode==TRADE_RETCODE_DONE || result.retcode==TRADE_RETCODE_DONE_PARTIAL)
      { journal_terminal="SUBMITTED"; result_status="EXECUTED"; }
   else if(result.retcode==TRADE_RETCODE_PLACED)
      { journal_terminal="SUBMITTED"; result_status="PENDING"; }
   else
      { journal_terminal="REJECTED"; result_status=api_result ? "BROKER_REJECTED" : "ORDERSEND_FAILED"; }
   if(!PersistTransition(journal_terminal,execution_uuid,decision_uuid,market_sequence,StringFormat("RETCODE_%u",result.retcode)))
      { AppendJournal("UNKNOWN_OUTCOME",execution_uuid,decision_uuid,market_sequence,"TERMINAL_STATE_PERSIST_FAILED"); Reject("Position",execution_uuid,"POSITION","TERMINAL_STATE_PERSIST_FAILED"); return; }
   if(!PersistResult(execution_uuid,result.order,result.retcode,result_status))
   {
      string publication_reason=StringFormat("RESULT_PERSIST_FAILED|retcode=%u|ticket=%I64u",result.retcode,result.order);
      if(!PersistTransition("UNKNOWN_OUTCOME",execution_uuid,decision_uuid,market_sequence,publication_reason))
         AppendJournal("UNKNOWN_OUTCOME",execution_uuid,decision_uuid,market_sequence,publication_reason);
      Reject("Execution result",execution_uuid,"POSITION","RESULT_PERSIST_FAILED");
      return;
   }
   if(journal_terminal=="SUBMITTED") Trace("OrderSend",result_status,execution_uuid,"NONE",StringFormat("RETCODE_%u",result.retcode));
   else Reject("OrderSend",execution_uuid,"ORDERSEND",StringFormat("RETCODE_%u_ERROR_%d",result.retcode,GetLastError()));
}
