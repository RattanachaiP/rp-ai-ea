//+------------------------------------------------------------------+
//|              RP_Market_State_Writer_V10_BB.mq5                   |
//|              Writes MA/RSI/MACD/BB + simple scores to JSON       |
//+------------------------------------------------------------------+
#property strict
#property version "1.16"

// Governed producer identity is owned by this source and cannot be configured.
#define MARKET_STATE_PRODUCER         "RP_AI_MT5_MARKET_STATE"
#define MARKET_STATE_PRODUCER_VERSION "V1"
#define MARKET_STATE_SCHEMA_VERSION   "1.0"
#define MARKET_STATE_SOURCE_UUID      "dc3777c6-cf0d-5a7b-bd58-8a5c44568475"

// Versioned model for the additional PR212 telemetry fields.  The digest
// identifies the exact trade-mode, tick-freshness, spread-quality, and EWMA
// slippage-expectation rules.  Price granularity is not called slippage.
#define TELEMETRY_POLICY_VERSION "RP_MT5_MODELED_TELEMETRY_V2"
#define TELEMETRY_POLICY_UUID    "deb04c7b-be67-5b44-a00c-02ece75326bd"
#define TELEMETRY_POLICY_DIGEST  "4a94734a04a574ecc58784da93e8dfe6c04e13726d1a7158b634db8d6c29998f"
#define TELEMETRY_SOURCE         "MT5_SYMBOL_TRADE_MODE_AND_LIVE_TICK_STREAM"

input string BaseFolderCommon = "RP_AI_EA\\shared\\"; // Common Files bridge path



// ================= ABSOLUTE D:\ BRIDGE FILE HELPERS =================
// Uses WinAPI so MT5 can read/write the same D:\RP_AI_EA\shared folder as Python.
// IMPORTANT: In EA settings, allow DLL imports. If disabled, EA will fall back to FILE_COMMON.
#import "kernel32.dll"
long CreateFileW(string lpFileName,uint dwDesiredAccess,uint dwShareMode,long lpSecurityAttributes,uint dwCreationDisposition,uint dwFlagsAndAttributes,long hTemplateFile);
bool WriteFile(long hFile,uchar &lpBuffer[],uint nNumberOfBytesToWrite,uint &lpNumberOfBytesWritten,long lpOverlapped);
bool ReadFile(long hFile,uchar &lpBuffer[],uint nNumberOfBytesToRead,uint &lpNumberOfBytesRead,long lpOverlapped);
uint GetFileSize(long hFile,long lpFileSizeHigh);
bool CloseHandle(long hObject);
bool CreateDirectoryW(string lpPathName,long lpSecurityAttributes);
bool MoveFileExW(string lpExistingFileName,string lpNewFileName,uint dwFlags);
#import

#define GENERIC_READ        0x80000000
#define GENERIC_WRITE       0x40000000
#define CREATE_ALWAYS       2
#define OPEN_EXISTING       3
#define FILE_ATTRIBUTE_NORMAL 0x00000080
#define INVALID_HANDLE_VALUE -1
#define MOVEFILE_REPLACE_EXISTING 0x1
#define MOVEFILE_WRITE_THROUGH    0x8

input bool UseAbsoluteDBridge = false;
input string AbsoluteBridgeRoot = "D:\\RP_AI_EA\\shared\\";
input bool FallbackToCommonFiles = true;

string BridgeRelativeFile(string filename)
{
   return BaseFolderCommon + _Symbol + "\\" + filename;
}

string BridgeAbsoluteFile(string filename)
{
   return AbsoluteBridgeRoot + _Symbol + "\\" + filename;
}

bool EnsureAbsoluteDirectory(string folder)
{
   string normalized = folder;
   StringReplace(normalized, "/", "\\");
   int len = StringLen(normalized);
   if(len <= 0)
      return false;

   // remove trailing backslash for step creation
   while(StringLen(normalized) > 0 && StringSubstr(normalized, StringLen(normalized)-1, 1) == "\\")
      normalized = StringSubstr(normalized, 0, StringLen(normalized)-1);

   // Create D:\RP_AI_EA then D:\RP_AI_EA\shared then symbol folder
   int start = StringFind(normalized, "\\");
   if(start < 0)
      return false;

   string current = StringSubstr(normalized, 0, start); // e.g. D:
   int pos = start + 1;
   while(true)
   {
      int next = StringFind(normalized, "\\", pos);
      string part;
      if(next < 0)
         part = StringSubstr(normalized, pos);
      else
         part = StringSubstr(normalized, pos, next - pos);

      if(StringLen(part) > 0)
      {
         current += "\\" + part;
         ResetLastError();
         CreateDirectoryW(current, 0);
      }

      if(next < 0)
         break;
      pos = next + 1;
   }
   return true;
}

bool WriteTextAbsolute(string full_path, string text)
{
   string folder = full_path;
   int lastSlash = -1;
   for(int i=StringLen(folder)-1; i>=0; i--)
   {
      if(StringSubstr(folder, i, 1) == "\\")
      { lastSlash = i; break; }
   }
   if(lastSlash > 0)
      EnsureAbsoluteDirectory(StringSubstr(folder, 0, lastSlash));

   ResetLastError();
   long h = CreateFileW(full_path, GENERIC_WRITE, FILE_SHARE_READ|FILE_SHARE_WRITE, 0, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, 0);
   if(h == INVALID_HANDLE_VALUE)
   {
      Print("ABS WRITE OPEN FAIL | ", full_path, " err=", GetLastError(), " | check Allow DLL imports and D: path permission");
      return false;
   }

   uchar bytes[];
   int n = StringToCharArray(text, bytes, 0, WHOLE_ARRAY, CP_UTF8);
   if(n > 0) n--; // remove null terminator
   uint written = 0;
   bool ok = WriteFile(h, bytes, (uint)n, written, 0);
   CloseHandle(h);
   if(!ok || written != (uint)n)
   {
      Print("ABS WRITE FAIL | ", full_path, " written=", written, " need=", n, " err=", GetLastError());
      return false;
   }
   return true;
}

bool WriteTextAbsoluteAtomic(string final_path, string text)
{
   string tmp_path = final_path + ".tmp";
   if(!WriteTextAbsolute(tmp_path, text))
      return false;
   ResetLastError();
   if(!MoveFileExW(tmp_path, final_path, MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH))
   {
      Print("ABS ATOMIC REPLACE FAIL | ", final_path, " err=", GetLastError());
      return false;
   }
   return true;
}

bool ReadTextAbsolute(string full_path, string &text)
{
   text = "";
   ResetLastError();
   long h = CreateFileW(full_path, GENERIC_READ, FILE_SHARE_READ|FILE_SHARE_WRITE, 0, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, 0);
   if(h == INVALID_HANDLE_VALUE)
   {
      Print("ABS READ OPEN FAIL | ", full_path, " err=", GetLastError(), " | check file exists / Allow DLL imports");
      return false;
   }

   uint size = GetFileSize(h, 0);
   if(size <= 0 || size > 1024*1024)
   {
      CloseHandle(h);
      Print("ABS READ SIZE FAIL | ", full_path, " size=", size);
      return false;
   }

   uchar bytes[];
   ArrayResize(bytes, (int)size);
   uint read = 0;
   bool ok = ReadFile(h, bytes, size, read, 0);
   CloseHandle(h);
   if(!ok || read <= 0)
   {
      Print("ABS READ FAIL | ", full_path, " read=", read, " err=", GetLastError());
      return false;
   }
   text = CharArrayToString(bytes, 0, (int)read, CP_UTF8);
   return StringLen(text) > 0;
}
// =====================================================================

input ENUM_TIMEFRAMES SignalTF = PERIOD_M3;
input int WriteEverySeconds = 1;

input int MA50Period = 50;
input int MA90Period = 90;
input int MA200Period = 200;
input int RSIPeriod = 14;
input int MACDFast = 12;
input int MACDSlow = 26;
input int MACDSignal = 9;
input int BBPeriod = 20;
input double BBDeviation = 2.0;
input double BBDeviation3 = 3.0;
input double BBDeviation4 = 4.0;

input bool PrintDebug = true;

int hMA50 = INVALID_HANDLE;
int hMA90 = INVALID_HANDLE;
int hMA200 = INVALID_HANDLE;
int hRSI = INVALID_HANDLE;
int hMACD = INVALID_HANDLE;
int hBB = INVALID_HANDLE;
int hBB3 = INVALID_HANDLE;
int hBB4 = INVALID_HANDLE;
datetime lastWrite = 0;
long g_market_state_sequence_id = 0;
string g_sequence_global_name = "";
bool WriteTextCommonAtomic(string finalPath, string text);
double g_previous_tick_mid = 0.0;
double g_slippage_expectation_ewma = 0.0;
int g_slippage_model_samples = 0;

string SequenceStateFile()
{
   return BridgeRelativeFile("market_state.sequence");
}

string WriterOwnerGlobalName()
{
   return "RP_AI.market_state.writer." + MARKET_STATE_SOURCE_UUID + "." + _Symbol;
}

bool ParseUnsignedLong(const string value, long &parsed)
{
   if(StringLen(value) <= 0)
      return false;
   for(int i=0; i<StringLen(value); i++)
      if(StringGetCharacter(value, i) < '0' || StringGetCharacter(value, i) > '9')
         return false;
   parsed = StringToInteger(value);
   return parsed >= 0 && IntegerToString(parsed) == value;
}

bool ReadCommonText(const string path, string &text)
{
   text = "";
   int h = FileOpen(path, FILE_READ|FILE_TXT|FILE_ANSI|FILE_COMMON|FILE_SHARE_READ);
   if(h == INVALID_HANDLE)
      return false;
   while(!FileIsEnding(h))
      text += FileReadString(h);
   FileClose(h);
   return true;
}

bool ReadPublishedSequence(long &sequence_id)
{
   string json;
   bool read_ok = false;
   if(UseAbsoluteDBridge)
      read_ok = ReadTextAbsolute(BridgeAbsoluteFile("market_state.json"), json);
   if(!read_ok && FallbackToCommonFiles)
      read_ok = ReadCommonText(BridgeRelativeFile("market_state.json"), json);
   if(!read_ok)
      return false;
   if(StringFind(json, "\"source_uuid\": \"" + MARKET_STATE_SOURCE_UUID + "\"") < 0 ||
      StringFind(json, "\"symbol\": \"" + _Symbol + "\"") < 0)
      return false;
   string marker = "\"sequence_id\": ";
   int begin = StringFind(json, marker);
   if(begin < 0) return false;
   begin += StringLen(marker);
   int finish = StringFind(json, ",", begin);
   if(finish < 0) return false;
   return ParseUnsignedLong(StringSubstr(json, begin, finish-begin), sequence_id);
}

bool LoadSequence()
{
   g_sequence_global_name = WriterOwnerGlobalName();
   // Set-on-condition is the terminal-wide mutex: a second Writer for this
   // governed producer and symbol cannot initialize concurrently.
   // A temporary terminal global is automatically discarded on terminal exit,
   // avoiding a stale owner after a crash while remaining live across charts.
   if(!GlobalVariableTemp(g_sequence_global_name))
      return false;
   if(!GlobalVariableSetOnCondition(g_sequence_global_name, (double)ChartID(), 0.0))
   {
      Print("DUPLICATE WRITER BLOCKED | owner=", (long)GlobalVariableGet(g_sequence_global_name));
      return false;
   }

   string state;
   long persisted = 0;
   bool state_exists = ReadCommonText(SequenceStateFile(), state);
   if(state_exists)
   {
      string prefix = "RP_SEQUENCE_V1|" + MARKET_STATE_SOURCE_UUID + "|" + _Symbol + "|";
      if(StringFind(state, prefix) != 0 ||
         !ParseUnsignedLong(StringSubstr(state, StringLen(prefix)), persisted))
      {
         Print("SEQUENCE STATE CORRUPT | source=FILE_COMMON:", SequenceStateFile());
         GlobalVariableSet(g_sequence_global_name, 0.0);
         return false; // fail closed; never guess within the same producer epoch
      }
   }

   // Reconcile the journal with the already committed publication.  This
   // closes the crash window between atomic publication and journal update.
   long published = 0;
   bool have_published = ReadPublishedSequence(published);
   g_market_state_sequence_id = MathMax(persisted, have_published ? published : 0);
   string storage = state_exists ? "FILE_COMMON_JOURNAL" : (have_published ? "MARKET_STATE_RECOVERY" : "EMPTY_STATE");
   Print("SEQUENCE RESTORE OK | previous=", g_market_state_sequence_id,
         " next=", g_market_state_sequence_id+1, " source=", storage);
   return true;
}

bool PersistSequence(const long sequence_id)
{
   string state = "RP_SEQUENCE_V1|" + MARKET_STATE_SOURCE_UUID + "|" + _Symbol + "|" + IntegerToString(sequence_id);
   return WriteTextCommonAtomic(SequenceStateFile(), state);
}

bool CalculateGovernedTelemetry(double &spread_points,
                                 double &market_session_quality,
                                 double &slippage_expectation,
                                 double &market_liquidity_quality)
{
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick))
      return false;

   const double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   const long trade_mode = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_MODE);
   const long tick_age_seconds = (long)TimeCurrent() - (long)tick.time;
   if(point <= 0.0 || tick.bid <= 0.0 || tick.ask < tick.bid ||
      tick.time <= 0 || tick_age_seconds < 0 || tick_age_seconds > 5)
      return false;

   spread_points = MathMax(0.0, (tick.ask - tick.bid) / point);
   if(trade_mode == SYMBOL_TRADE_MODE_FULL)
      market_session_quality = 1.0;
   else if(trade_mode == SYMBOL_TRADE_MODE_LONGONLY || trade_mode == SYMBOL_TRADE_MODE_SHORTONLY)
      market_session_quality = 0.5;
   else // CLOSEONLY and DISABLED cannot open an unrestricted new position.
      market_session_quality = 0.0;

   // Liquidity is full through 20 points, degrades linearly, and is zero at
   // the PR212 maximum of 50 points.  Invalid/stale ticks already fail closed.
   if(spread_points <= 20.0)
      market_liquidity_quality = 1.0;
   else if(spread_points >= 50.0)
      market_liquidity_quality = 0.0;
   else
      market_liquidity_quality = (50.0 - spread_points) / 30.0;
   if(market_session_quality <= 0.0)
      market_liquidity_quality = 0.0;

   // Model expected slippage from live mid-price movement, not from spread or
   // SYMBOL_TRADE_TICK_SIZE.  At least one transition is required; no numeric
   // placeholder escapes before the model has an observation.
   const double current_mid = (tick.bid + tick.ask) / 2.0;
   if(g_previous_tick_mid <= 0.0)
   {
      g_previous_tick_mid = current_mid;
      return false;
   }
   const double movement_points = MathAbs(current_mid - g_previous_tick_mid) / point;
   g_previous_tick_mid = current_mid;
   if(g_slippage_model_samples == 0)
      g_slippage_expectation_ewma = movement_points;
   else
      g_slippage_expectation_ewma = 0.2 * movement_points + 0.8 * g_slippage_expectation_ewma;
   g_slippage_model_samples++;
   slippage_expectation = g_slippage_expectation_ewma;
   return true;
}

bool CopyOne(int handle, int bufferIndex, double &value)
{
   double arr[];
   ArraySetAsSeries(arr, true);
   int copied = CopyBuffer(handle, bufferIndex, 0, 1, arr);
   if(copied <= 0)
      return false;
   value = arr[0];
   return true;
}

string TFToString(ENUM_TIMEFRAMES tf)
{
   if(tf == PERIOD_M1) return "M1";
   if(tf == PERIOD_M3) return "M3";
   if(tf == PERIOD_M5) return "M5";
   if(tf == PERIOD_M15) return "M15";
   if(tf == PERIOD_H1) return "H1";
   if(tf == PERIOD_H4) return "H4";
   return EnumToString(tf);
}


// ================= COMMON FILES ATOMIC WRITE HELPER =================
bool WriteTextCommonAtomic(string finalPath, string text)
{
   string tmpPath = finalPath + ".tmp";

   for(int attempt = 1; attempt <= 3; attempt++)
   {
      ResetLastError();
      int h = FileOpen(tmpPath, FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON | FILE_SHARE_READ);
      if(h == INVALID_HANDLE)
      {
         Print("MARKET STATE TMP OPEN FAIL | attempt=", attempt, " path=", tmpPath, " err=", GetLastError());
         Sleep(50 + attempt * 50);
         continue;
      }

      uint written = FileWriteString(h, text);
      FileFlush(h);
      FileClose(h);
      if(written != (uint)StringLen(text))
      {
         Print("MARKET STATE TMP WRITE FAIL | attempt=", attempt, " path=", tmpPath);
         Sleep(50 + attempt * 50);
         continue;
      }

      // Same-directory rename with replacement is the publication commit point;
      // readers see either the old complete document or the new complete one.
      ResetLastError();
      if(FileMove(tmpPath, FILE_COMMON, finalPath, FILE_COMMON|FILE_REWRITE))
      {
         Print("MARKET STATE ATOMIC WRITE OK | attempt=", attempt);
         return true;
      }

      Print("MARKET STATE RETRY WRITE | atomic move fail attempt=", attempt,
            " err=", GetLastError());
      Sleep(50 + attempt * 50);
   }

   FileDelete(tmpPath, FILE_COMMON);
   Print("MARKET STATE FINAL FAIL | path=", finalPath, " err=", GetLastError());
   return false;
}
// =====================================================================

int OnInit()
{
   hMA50 = iMA(_Symbol, SignalTF, MA50Period, 0, MODE_EMA, PRICE_CLOSE);
   hMA90 = iMA(_Symbol, SignalTF, MA90Period, 0, MODE_EMA, PRICE_CLOSE);
   hMA200 = iMA(_Symbol, SignalTF, MA200Period, 0, MODE_EMA, PRICE_CLOSE);
   hRSI = iRSI(_Symbol, SignalTF, RSIPeriod, PRICE_CLOSE);
   hMACD = iMACD(_Symbol, SignalTF, MACDFast, MACDSlow, MACDSignal, PRICE_CLOSE);
   hBB = iBands(_Symbol, SignalTF, BBPeriod, 0, BBDeviation, PRICE_CLOSE);
   hBB3 = iBands(_Symbol, SignalTF, BBPeriod, 0, BBDeviation3, PRICE_CLOSE);
   hBB4 = iBands(_Symbol, SignalTF, BBPeriod, 0, BBDeviation4, PRICE_CLOSE);

   if(hMA50 == INVALID_HANDLE || hMA90 == INVALID_HANDLE || hMA200 == INVALID_HANDLE || hRSI == INVALID_HANDLE || hMACD == INVALID_HANDLE || hBB == INVALID_HANDLE || hBB3 == INVALID_HANDLE || hBB4 == INVALID_HANDLE)
   {
      Print("INDICATORS HANDLE FAILED | err=", GetLastError());
      return INIT_FAILED;
   }
   if(!LoadSequence())
   {
      Print("SEQUENCE STATE FAILED | err=", GetLastError());
      return INIT_FAILED;
   }

   Print("RP Market State Writer V14 TIME SYNC STANDARD V1 started | symbol=", _Symbol, " tf=", TFToString(SignalTF), " | common_market_state_path=", BridgeRelativeFile("market_state.json"));
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(StringLen(g_sequence_global_name) > 0 &&
      (long)GlobalVariableGet(g_sequence_global_name) == ChartID())
      GlobalVariableSet(g_sequence_global_name, 0.0);
   if(hMA50 != INVALID_HANDLE) IndicatorRelease(hMA50);
   if(hMA90 != INVALID_HANDLE) IndicatorRelease(hMA90);
   if(hMA200 != INVALID_HANDLE) IndicatorRelease(hMA200);
   if(hRSI != INVALID_HANDLE) IndicatorRelease(hRSI);
   if(hMACD != INVALID_HANDLE) IndicatorRelease(hMACD);
   if(hBB != INVALID_HANDLE) IndicatorRelease(hBB);
   if(hBB3 != INVALID_HANDLE) IndicatorRelease(hBB3);
   if(hBB4 != INVALID_HANDLE) IndicatorRelease(hBB4);
}

void OnTick()
{
   datetime now = TimeCurrent();
   if(now - lastWrite < WriteEverySeconds)
      return;
   lastWrite = now;

   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double ma50=0, ma90=0, ma200=0, rsi=0, macdMain=0, macdSignal=0;
   double bbUpper=0, bbMiddle=0, bbLower=0;
   double bb3Upper=0, bb3Middle=0, bb3Lower=0;
   double bb4Upper=0, bb4Middle=0, bb4Lower=0;

   bool ok = true;
   ok &= CopyOne(hMA50, 0, ma50);
   ok &= CopyOne(hMA90, 0, ma90);
   ok &= CopyOne(hMA200, 0, ma200);
   ok &= CopyOne(hRSI, 0, rsi);
   ok &= CopyOne(hMACD, 0, macdMain);
   ok &= CopyOne(hMACD, 1, macdSignal);
   // iBands buffers: 0=middle, 1=upper, 2=lower
   ok &= CopyOne(hBB, 0, bbMiddle);
   ok &= CopyOne(hBB, 1, bbUpper);
   ok &= CopyOne(hBB, 2, bbLower);
   ok &= CopyOne(hBB3, 0, bb3Middle);
   ok &= CopyOne(hBB3, 1, bb3Upper);
   ok &= CopyOne(hBB3, 2, bb3Lower);
   ok &= CopyOne(hBB4, 0, bb4Middle);
   ok &= CopyOne(hBB4, 1, bb4Upper);
   ok &= CopyOne(hBB4, 2, bb4Lower);

   if(!ok || bid <= 0 || ma50 <= 0 || bbUpper <= 0 || bbLower <= 0 || bb4Upper <= 0 || bb4Lower <= 0)
   {
      Print("BLOCK | cannot read indicator buffers | err=", GetLastError());
      return;
   }

   double macdHist = macdMain - macdSignal;
   int buyScore = 0;
   int sellScore = 0;

   if(bid > ma50) buyScore++; else sellScore++;
   if(ma50 > ma90) buyScore++; else sellScore++;
   if(ma90 > ma200) buyScore++; else sellScore++;
   if(rsi > 55) buyScore++;
   if(rsi < 45) sellScore++;
   if(macdHist > 0) buyScore++;
   if(macdHist < 0) sellScore++;
   if(bid <= bbLower) buyScore++;
   if(bid >= bbUpper) sellScore++;

   datetime barTime = iTime(_Symbol, SignalTF, 0);
   long heartbeatUnix = (long)now;
   long nextSequenceId = g_market_state_sequence_id + 1;
   double spreadPoints=0, marketSessionQuality=0, slippageExpectation=0, marketLiquidityQuality=0;
   if(!CalculateGovernedTelemetry(spreadPoints, marketSessionQuality,
                                   slippageExpectation, marketLiquidityQuality))
   {
      Print("BLOCK | governed telemetry unavailable | err=", GetLastError());
      return;
   }

   string json = "{\n";
   json += "  \"producer\": \"" + MARKET_STATE_PRODUCER + "\",\n";
   json += "  \"producer_version\": \"" + MARKET_STATE_PRODUCER_VERSION + "\",\n";
   json += "  \"schema_version\": \"" + MARKET_STATE_SCHEMA_VERSION + "\",\n";
   json += "  \"source_uuid\": \"" + MARKET_STATE_SOURCE_UUID + "\",\n";
   json += "  \"symbol\": \"" + _Symbol + "\",\n";
   json += "  \"timeframe\": \"" + TFToString(SignalTF) + "\",\n";
   json += "  \"time_sync\": \"RP_TIME_SYNC_STANDARD_V1\",\n";
   json += "  \"heartbeat_unix\": " + IntegerToString(heartbeatUnix) + ",\n";
   json += "  \"sequence_id\": " + IntegerToString(nextSequenceId) + ",\n";
   json += "  \"server_time\": \"" + TimeToString(now, TIME_DATE|TIME_SECONDS) + "\",\n";
   json += "  \"bar_time\": \"" + TimeToString(barTime, TIME_DATE|TIME_SECONDS) + "\",\n";
   json += "  \"bid\": " + DoubleToString(bid, _Digits) + ",\n";
   json += "  \"ask\": " + DoubleToString(ask, _Digits) + ",\n";
   json += "  \"spread_points\": " + DoubleToString(spreadPoints, 3) + ",\n";
   json += "  \"market_session_quality\": " + DoubleToString(marketSessionQuality, 6) + ",\n";
   json += "  \"slippage_expectation\": " + DoubleToString(slippageExpectation, 3) + ",\n";
   json += "  \"market_liquidity_quality\": " + DoubleToString(marketLiquidityQuality, 6) + ",\n";
   json += "  \"telemetry_policy_uuid\": \"" + TELEMETRY_POLICY_UUID + "\",\n";
   json += "  \"telemetry_policy_digest\": \"" + TELEMETRY_POLICY_DIGEST + "\",\n";
   json += "  \"telemetry_policy_version\": \"" + TELEMETRY_POLICY_VERSION + "\",\n";
   json += "  \"telemetry_source_provenance\": \"" + TELEMETRY_SOURCE + "\",\n";
   json += "  \"ma50\": " + DoubleToString(ma50, _Digits) + ",\n";
   json += "  \"ma90\": " + DoubleToString(ma90, _Digits) + ",\n";
   json += "  \"ma200\": " + DoubleToString(ma200, _Digits) + ",\n";
   json += "  \"rsi\": " + DoubleToString(rsi, 2) + ",\n";
   json += "  \"macd_main\": " + DoubleToString(macdMain, 6) + ",\n";
   json += "  \"macd_signal\": " + DoubleToString(macdSignal, 6) + ",\n";
   json += "  \"macd_hist\": " + DoubleToString(macdHist, 6) + ",\n";
   json += "  \"bb_upper\": " + DoubleToString(bbUpper, _Digits) + ",\n";
   json += "  \"bb_middle\": " + DoubleToString(bbMiddle, _Digits) + ",\n";
   json += "  \"bb_lower\": " + DoubleToString(bbLower, _Digits) + ",\n";
   json += "  \"bb3_upper\": " + DoubleToString(bb3Upper, _Digits) + ",\n";
   json += "  \"bb3_middle\": " + DoubleToString(bb3Middle, _Digits) + ",\n";
   json += "  \"bb3_lower\": " + DoubleToString(bb3Lower, _Digits) + ",\n";
   json += "  \"bb4_upper\": " + DoubleToString(bb4Upper, _Digits) + ",\n";
   json += "  \"bb4_middle\": " + DoubleToString(bb4Middle, _Digits) + ",\n";
   json += "  \"bb4_lower\": " + DoubleToString(bb4Lower, _Digits) + ",\n";
   json += "  \"buyScore\": " + IntegerToString(buyScore) + ",\n";
   json += "  \"sellScore\": " + IntegerToString(sellScore) + "\n";
   json += "}\n";

   bool wrote = false;
   string path = BridgeAbsoluteFile("market_state.json");

   if(UseAbsoluteDBridge)
      wrote = WriteTextAbsoluteAtomic(path, json);

   if(!wrote && FallbackToCommonFiles)
   {
      string commonPath = BridgeRelativeFile("market_state.json");
      if(WriteTextCommonAtomic(commonPath, json))
      {
         wrote = true;
         path = "COMMON:" + commonPath;
      }
      else
      {
         Print("COMMON WRITE FAIL | ", commonPath, " err=", GetLastError());
      }
   }

   if(!wrote)
   {
      Print("WRITE FAIL | no bridge output written | common_path=", BridgeRelativeFile("market_state.json"));
      return;
   }

   // The publication is the commit point.  Journal only committed IDs.  If
   // journaling fails, stop this producer; OnInit can recover the committed ID
   // from market_state.json and will never publish a lower value.
   g_market_state_sequence_id = nextSequenceId;
   if(!PersistSequence(nextSequenceId))
   {
      Print("SEQUENCE PERSIST FAIL CLOSED | sequence_id=", nextSequenceId,
            " err=", GetLastError());
      ExpertRemove();
      return;
   }

   if(PrintDebug)
      Print("MARKET STATE WRITTEN | ", _Symbol,
            " path=", path,
            " heartbeat_unix=", heartbeatUnix,
            " sequence_id=", g_market_state_sequence_id,
            " bid=", DoubleToString(bid, _Digits),
            " BB2=", DoubleToString(bbLower, _Digits), "/", DoubleToString(bbMiddle, _Digits), "/", DoubleToString(bbUpper, _Digits),
            " BB4=", DoubleToString(bb4Lower, _Digits), "/", DoubleToString(bb4Middle, _Digits), "/", DoubleToString(bb4Upper, _Digits),
            " score=", buyScore, ":", sellScore);
}
//+------------------------------------------------------------------+
