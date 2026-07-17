//+------------------------------------------------------------------+
//| RP AI Executor V28 -- minimum execution path                    |
//+------------------------------------------------------------------+
#property strict
#property version   "28.01"
#property description "V28 executor: decision.json + market_state.json + broker safety only."

#include <Trade/Trade.mqh>

// Both files are intentionally read from the MT5 Common Files directory.
#define DECISION_FILE     "decision.json"
#define MARKET_STATE_FILE "market_state.json"

input int    InpMaxMarketStateAgeSeconds = 15;
input double InpExposureCapLots           = 1.00;
input bool   InpEmergencyDisable          = false;
input long   InpMagic                     = 2800001;

CTrade g_trade;

string ReadCommonFile(const string file_name)
{
   int handle = FileOpen(file_name, FILE_READ | FILE_TXT | FILE_COMMON | FILE_ANSI);
   if(handle == INVALID_HANDLE) return "";

   string text = "";
   while(!FileIsEnding(handle)) text += FileReadString(handle) + "\n";
   FileClose(handle);
   return text;
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

bool MarketStateFresh(string &reason)
{
   string market = ReadCommonFile(MARKET_STATE_FILE);
   if(market == "") { reason = "MARKET_STATE_UNREADABLE"; return false; }
   if(!JsonBool(market, "market_state_fresh", true)) { reason = "STALE_MARKET_STATE"; return false; }

   datetime heartbeat = (datetime)JsonNumber(market, "heartbeat_unix");
   int age = (int)(TimeCurrent() - heartbeat);
   if(heartbeat <= 0 || age < 0 || age > InpMaxMarketStateAgeSeconds)
   {
      reason = "STALE_MARKET_STATE";
      return false;
   }
   return true;
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

   string json = ReadCommonFile(DECISION_FILE);
   if(json == "") { Print("DECISION_PAYLOAD_UNREADABLE"); return; }
   if(JsonString(json, "decision") != "TRADE") return;
   if(!JsonBool(json, "entry_allowed")) return;

   string action = JsonString(json, "action");
   StringToUpper(action);
   if(action != "BUY" && action != "SELL") { Print("INVALID_ACTION"); return; }

   string reason;
   if(!MarketStateFresh(reason)) { Print(reason); return; }

   string symbol = JsonString(json, "symbol");
   double lot = JsonNumber(json, "lot", JsonNumber(json, "position_size"));
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
