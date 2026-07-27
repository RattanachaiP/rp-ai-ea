#property strict
#property version "13.1"

// Canonical, governed identity of the MT5 market-state feed.  Keep these
// values here: consumers must validate them, not supply or repair them.
#define MARKET_STATE_PRODUCER         "RP_AI_MT5_MARKET_STATE"
#define MARKET_STATE_PRODUCER_VERSION "V1"
#define MARKET_STATE_SCHEMA_VERSION   "1.0"
#define MARKET_STATE_SOURCE_UUID      "dc3777c6-cf0d-5a7b-bd58-8a5c44568475"

input string InpMarketStatePath = "RP_AI_EA\\shared\\XAUUSD\\market_state.json";
input string InpSymbol = "XAUUSD";
input uint InpPublishIntervalMilliseconds = 250;

ulong g_market_state_sequence = 0;

// The existing V13 signal calculations pass their governed telemetry fields
// to this publication boundary.  Identity is deliberately not an argument:
// this producer is the sole authority which writes it.
string BuildMarketStateJson(const string symbol,
                            const double bid,
                            const double spread_points,
                            const double market_session_quality,
                            const double slippage_expectation,
                            const double market_liquidity_quality,
                            const string telemetry_json)
{
   const long heartbeat_unix = (long)TimeGMT();
   g_market_state_sequence++;

   string json = "{";
   json += "\"producer\":\"" + MARKET_STATE_PRODUCER + "\",";
   json += "\"producer_version\":\"" + MARKET_STATE_PRODUCER_VERSION + "\",";
   json += "\"schema_version\":\"" + MARKET_STATE_SCHEMA_VERSION + "\",";
   json += "\"source_uuid\":\"" + MARKET_STATE_SOURCE_UUID + "\",";
   json += "\"symbol\":\"" + symbol + "\",";
   json += "\"heartbeat_unix\":" + IntegerToString(heartbeat_unix) + ",";
   json += "\"sequence_id\":" + IntegerToString((long)g_market_state_sequence) + ",";
   json += "\"bid\":" + DoubleToString(bid, (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS)) + ",";
   json += "\"spread_points\":" + DoubleToString(spread_points, 3) + ",";
   json += "\"market_session_quality\":" + DoubleToString(market_session_quality, 6) + ",";
   json += "\"slippage_expectation\":" + DoubleToString(slippage_expectation, 3) + ",";
   json += "\"market_liquidity_quality\":" + DoubleToString(market_liquidity_quality, 6);
   if(StringLen(telemetry_json) > 0)
      json += "," + telemetry_json;
   return json + "}";
}

bool PublishMarketState(const string payload)
{
   const string temporary_path = InpMarketStatePath + ".tmp";
   int handle = FileOpen(temporary_path, FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON);
   if(handle == INVALID_HANDLE)
      return false;

   FileWriteString(handle, payload);
   FileFlush(handle);
   FileClose(handle);

   // Publication remains atomic from the reader's perspective.  A failed
   // replacement leaves no partially written canonical payload.
   if(!FileMove(temporary_path, FILE_COMMON, InpMarketStatePath, FILE_COMMON | FILE_REWRITE))
   {
      FileDelete(temporary_path, FILE_COMMON);
      return false;
   }
   return true;
}

int OnInit()
{
   if(InpSymbol != "XAUUSD" || InpPublishIntervalMilliseconds == 0)
      return INIT_PARAMETERS_INCORRECT;
   EventSetMillisecondTimer((int)InpPublishIntervalMilliseconds);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   EventKillTimer();
}

void OnTimer()
{
   MqlTick tick;
   if(!SymbolInfoTick(InpSymbol, tick) || tick.bid <= 0.0)
      return;

   const double point = SymbolInfoDouble(InpSymbol, SYMBOL_POINT);
   if(point <= 0.0)
      return;

   const double spread_points = MathMax(0.0, (tick.ask - tick.bid) / point);
   const long session_state = SymbolInfoInteger(InpSymbol, SYMBOL_TRADE_MODE);
   const bool tradeable = (session_state != SYMBOL_TRADE_MODE_DISABLED);
   const double session_quality = tradeable ? 1.0 : 0.0;
   const double liquidity_quality = (tradeable && tick.ask > tick.bid) ? 1.0 : 0.0;

   PublishMarketState(BuildMarketStateJson(
      InpSymbol, tick.bid, spread_points, session_quality, spread_points,
      liquidity_quality, ""));
}
