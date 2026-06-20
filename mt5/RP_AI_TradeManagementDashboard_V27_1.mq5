//+------------------------------------------------------------------+
//| RP AI Trade Management Dashboard V27.1                           |
//| On-chart MT5 dashboard for post-entry trade management only.      |
//+------------------------------------------------------------------+
#property strict
#property version   "27.10"
#property description "V27.1 Trade Management Dashboard - post-entry management only"

#include <Trade/Trade.mqh>

input string InpDashboardJsonFile = "trade_management_dashboard.json";
input string InpProfilesFolder    = "dashboard_profiles";
input string InpDefaultProfile    = "Balanced";
input int    InpChartCorner       = CORNER_LEFT_UPPER;
input int    InpX                 = 12;
input int    InpY                 = 24;
input int    InpTimerSeconds      = 2;
input bool   InpManageOpenTrades  = true;

#define RP_DASH_SCHEMA "V27_TRADE_MANAGEMENT_DASHBOARD_SCHEMA_1"
#define RP_PREFIX      "RP_V271_TMD_"

struct DashboardConfig
{
   string active_profile;
   bool enabled;
   double hard_loss_cap_usd_001_lot;
   double max_floating_loss_usd_001_lot;
   bool breakeven_enable;
   double breakeven_trigger_usd_001_lot;
   double breakeven_offset_usd_001_lot;
   bool trailing_enable;
   double trailing_start_usd_001_lot;
   double trailing_distance_usd_001_lot;
   double trailing_step_usd_001_lot;
   double lock1_trigger;
   double lock1_lock;
   double lock2_trigger;
   double lock2_lock;
   double lock3_trigger;
   double lock3_lock;
   bool runner_enable;
   int runner_timeout_seconds;
   int maximum_seconds;
   bool partial_enable;
   int partial_level_1_percent;
   string load_status;
   bool fallback_defaults_used;
};

DashboardConfig g_cfg;
CTrade g_trade;
datetime g_last_load = 0;
string g_status = "starting";

void ApplyBackwardCompatibleDefaults(DashboardConfig &cfg)
{
   cfg.active_profile = InpDefaultProfile;
   cfg.enabled = true;
   cfg.hard_loss_cap_usd_001_lot = 1.00;
   cfg.max_floating_loss_usd_001_lot = 0.80;
   cfg.breakeven_enable = true;
   cfg.breakeven_trigger_usd_001_lot = 0.50;
   cfg.breakeven_offset_usd_001_lot = 0.00;
   cfg.trailing_enable = true;
   cfg.trailing_start_usd_001_lot = 0.80;
   cfg.trailing_distance_usd_001_lot = 0.30;
   cfg.trailing_step_usd_001_lot = 0.10;
   cfg.lock1_trigger = 0.50; cfg.lock1_lock = 0.00;
   cfg.lock2_trigger = 0.80; cfg.lock2_lock = 0.10;
   cfg.lock3_trigger = 1.20; cfg.lock3_lock = 0.40;
   cfg.runner_enable = true;
   cfg.runner_timeout_seconds = 45;
   cfg.maximum_seconds = 0;
   cfg.partial_enable = false;
   cfg.partial_level_1_percent = 0;
   cfg.load_status = "embedded V26.6-compatible defaults";
   cfg.fallback_defaults_used = true;
}

string ReadCommonFile(const string file_name)
{
   int handle = FileOpen(file_name, FILE_READ | FILE_TXT | FILE_COMMON | FILE_ANSI);
   if(handle == INVALID_HANDLE)
      return "";
   string text = "";
   while(!FileIsEnding(handle))
      text += FileReadString(handle) + "\n";
   FileClose(handle);
   return text;
}

bool WriteCommonFile(const string file_name, const string text)
{
   int handle = FileOpen(file_name, FILE_WRITE | FILE_TXT | FILE_COMMON | FILE_ANSI);
   if(handle == INVALID_HANDLE)
      return false;
   FileWriteString(handle, text);
   FileClose(handle);
   return true;
}

string JsonString(const string json, const string key, const string fallback)
{
   string pattern = "\"" + key + "\"";
   int p = StringFind(json, pattern);
   if(p < 0) return fallback;
   int c = StringFind(json, ":", p);
   int q1 = StringFind(json, "\"", c + 1);
   int q2 = StringFind(json, "\"", q1 + 1);
   if(c < 0 || q1 < 0 || q2 < 0) return fallback;
   return StringSubstr(json, q1 + 1, q2 - q1 - 1);
}

double JsonNumber(const string json, const string key, const double fallback)
{
   string pattern = "\"" + key + "\"";
   int p = StringFind(json, pattern);
   if(p < 0) return fallback;
   int c = StringFind(json, ":", p);
   if(c < 0) return fallback;
   int e = c + 1;
   while(e < StringLen(json))
   {
      ushort ch = StringGetCharacter(json, e);
      if((ch >= '0' && ch <= '9') || ch == '-' || ch == '+' || ch == '.') e++;
      else if(ch == ' ' || ch == '\t' || ch == '\r' || ch == '\n') e++;
      else break;
   }
   return StringToDouble(StringSubstr(json, c + 1, e - c - 1));
}

bool JsonBool(const string json, const string key, const bool fallback)
{
   string pattern = "\"" + key + "\"";
   int p = StringFind(json, pattern);
   if(p < 0) return fallback;
   int c = StringFind(json, ":", p);
   if(c < 0) return fallback;
   string tail = StringSubstr(json, c + 1, 8);
   StringToLower(tail);
   if(StringFind(tail, "true") >= 0) return true;
   if(StringFind(tail, "false") >= 0) return false;
   return fallback;
}

void OverlayJson(DashboardConfig &cfg, const string json)
{
   cfg.active_profile = JsonString(json, "active_profile", cfg.active_profile);
   cfg.enabled = JsonBool(json, "enabled", cfg.enabled);
   cfg.hard_loss_cap_usd_001_lot = JsonNumber(json, "hard_loss_cap_usd_001_lot", cfg.hard_loss_cap_usd_001_lot);
   cfg.max_floating_loss_usd_001_lot = JsonNumber(json, "max_floating_loss_usd_001_lot", cfg.max_floating_loss_usd_001_lot);
   cfg.breakeven_enable = JsonBool(json, "enable", cfg.breakeven_enable);
   cfg.breakeven_trigger_usd_001_lot = JsonNumber(json, "trigger_usd_001_lot", cfg.breakeven_trigger_usd_001_lot);
   cfg.breakeven_offset_usd_001_lot = JsonNumber(json, "offset_usd_001_lot", cfg.breakeven_offset_usd_001_lot);
   cfg.trailing_enable = JsonBool(json, "dynamic_trail", cfg.trailing_enable);
   cfg.trailing_start_usd_001_lot = JsonNumber(json, "start_usd_001_lot", cfg.trailing_start_usd_001_lot);
   cfg.trailing_distance_usd_001_lot = JsonNumber(json, "distance_usd_001_lot", cfg.trailing_distance_usd_001_lot);
   cfg.trailing_step_usd_001_lot = JsonNumber(json, "step_usd_001_lot", cfg.trailing_step_usd_001_lot);
   cfg.lock1_trigger = JsonNumber(json, "trigger", cfg.lock1_trigger);
   cfg.lock1_lock = JsonNumber(json, "lock", cfg.lock1_lock);
   cfg.runner_enable = JsonBool(json, "enable_runner", cfg.runner_enable);
   cfg.runner_timeout_seconds = (int)JsonNumber(json, "runner_timeout_seconds", cfg.runner_timeout_seconds);
   cfg.maximum_seconds = (int)JsonNumber(json, "maximum_seconds", cfg.maximum_seconds);
   cfg.partial_enable = JsonBool(json, "partial_exits_enable", cfg.partial_enable);
   cfg.partial_level_1_percent = (int)JsonNumber(json, "partial_level_1_percent", cfg.partial_level_1_percent);
}

bool LoadDashboardProfile()
{
   ApplyBackwardCompatibleDefaults(g_cfg);
   string dashboard = ReadCommonFile(InpDashboardJsonFile);
   if(dashboard != "")
   {
      OverlayJson(g_cfg, dashboard);
      g_cfg.load_status = "loaded dashboard json";
      g_cfg.fallback_defaults_used = false;
   }
   string profile_file = InpProfilesFolder + "\\" + g_cfg.active_profile + ".json";
   string profile = ReadCommonFile(profile_file);
   if(profile != "")
   {
      OverlayJson(g_cfg, profile);
      g_cfg.load_status = "loaded dashboard + profile json";
      g_cfg.fallback_defaults_used = false;
   }
   g_last_load = TimeCurrent();
   return !g_cfg.fallback_defaults_used;
}

string DashboardJson()
{
   return StringFormat("{\n  \"schema_version\": \"%s\",\n  \"active_profile\": \"%s\",\n  \"enabled\": %s,\n  \"risk\": {\"hard_loss_cap_usd_001_lot\": %.2f, \"max_floating_loss_usd_001_lot\": %.2f},\n  \"breakeven\": {\"enable\": %s, \"trigger_usd_001_lot\": %.2f, \"offset_usd_001_lot\": %.2f},\n  \"trailing\": {\"enable\": %s, \"start_usd_001_lot\": %.2f, \"distance_usd_001_lot\": %.2f, \"step_usd_001_lot\": %.2f},\n  \"runner\": {\"enable_runner\": %s, \"runner_timeout_seconds\": %d},\n  \"time_exits\": {\"maximum_seconds\": %d}\n}\n",
                       RP_DASH_SCHEMA, g_cfg.active_profile, g_cfg.enabled ? "true" : "false",
                       g_cfg.hard_loss_cap_usd_001_lot, g_cfg.max_floating_loss_usd_001_lot,
                       g_cfg.breakeven_enable ? "true" : "false", g_cfg.breakeven_trigger_usd_001_lot, g_cfg.breakeven_offset_usd_001_lot,
                       g_cfg.trailing_enable ? "true" : "false", g_cfg.trailing_start_usd_001_lot, g_cfg.trailing_distance_usd_001_lot, g_cfg.trailing_step_usd_001_lot,
                       g_cfg.runner_enable ? "true" : "false", g_cfg.runner_timeout_seconds, g_cfg.maximum_seconds);
}

void SaveDashboardProfile()
{
   string profile_file = InpProfilesFolder + "\\" + g_cfg.active_profile + ".json";
   bool ok1 = WriteCommonFile(InpDashboardJsonFile, DashboardJson());
   bool ok2 = WriteCommonFile(profile_file, DashboardJson());
   g_status = (ok1 && ok2) ? "saved profile json" : "save failed - check Common Files permissions";
}

void CreateButton(const string name, const string text, const int x, const int y, const int w)
{
   ObjectCreate(0, name, OBJ_BUTTON, 0, 0, 0);
   ObjectSetInteger(0, name, OBJPROP_CORNER, InpChartCorner);
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, y);
   ObjectSetInteger(0, name, OBJPROP_XSIZE, w);
   ObjectSetInteger(0, name, OBJPROP_YSIZE, 22);
   ObjectSetString(0, name, OBJPROP_TEXT, text);
}

void CreateLabel(const string name, const int x, const int y)
{
   ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);
   ObjectSetInteger(0, name, OBJPROP_CORNER, InpChartCorner);
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, y);
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, 9);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clrWhite);
}

void DrawDashboard()
{
   CreateLabel(RP_PREFIX + "TITLE", InpX, InpY);
   CreateButton(RP_PREFIX + "SAVE", "Save Profile JSON", InpX, InpY + 22, 130);
   CreateButton(RP_PREFIX + "LOAD", "Load/Reload JSON", InpX + 136, InpY + 22, 130);
   CreateButton(RP_PREFIX + "TOGGLE", g_cfg.enabled ? "Disable TM" : "Enable TM", InpX + 272, InpY + 22, 90);
   CreateLabel(RP_PREFIX + "BODY", InpX, InpY + 52);
   UpdateDashboardText();
}

void UpdateDashboardText()
{
   ObjectSetString(0, RP_PREFIX + "TITLE", OBJPROP_TEXT, "V27.1 Trade Management Dashboard (NO AI direction/entry controls)");
   ObjectSetString(0, RP_PREFIX + "BODY", OBJPROP_TEXT,
                   StringFormat("Profile=%s | Enabled=%s | Load=%s | Fallback=%s\nHardCap=$%.2f/0.01 | BE=%s @ $%.2f | Trail=%s start $%.2f dist $%.2f\nExecutor runtime values active: %s | Last reload: %s",
                                g_cfg.active_profile, g_cfg.enabled ? "true" : "false", g_cfg.load_status,
                                g_cfg.fallback_defaults_used ? "true" : "false", g_cfg.hard_loss_cap_usd_001_lot,
                                g_cfg.breakeven_enable ? "on" : "off", g_cfg.breakeven_trigger_usd_001_lot,
                                g_cfg.trailing_enable ? "on" : "off", g_cfg.trailing_start_usd_001_lot,
                                g_cfg.trailing_distance_usd_001_lot, InpManageOpenTrades ? "yes" : "display only",
                                TimeToString(g_last_load, TIME_DATE | TIME_SECONDS)));
}

double MoneyToPriceDistance(const double money_001_lot, const double volume)
{
   double tick_value = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tick_value <= 0.0 || tick_size <= 0.0 || volume <= 0.0) return 0.0;
   double scaled_money = money_001_lot * (volume / 0.01);
   return (scaled_money / tick_value) * tick_size;
}

void ManageOpenPositions()
{
   if(!InpManageOpenTrades || !g_cfg.enabled) return;
   for(int i = PositionsTotal() - 1; i >= 0; --i)
   {
      ulong ticket = PositionGetTicket(i);
      if(!PositionSelectByTicket(ticket) || PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      long type = PositionGetInteger(POSITION_TYPE);
      double volume = PositionGetDouble(POSITION_VOLUME);
      double open = PositionGetDouble(POSITION_PRICE_OPEN);
      double sl = PositionGetDouble(POSITION_SL);
      double tp = PositionGetDouble(POSITION_TP);
      double profit = PositionGetDouble(POSITION_PROFIT);
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double price = (type == POSITION_TYPE_BUY) ? bid : ask;

      if(profit <= -g_cfg.hard_loss_cap_usd_001_lot * (volume / 0.01))
      {
         g_trade.PositionClose(ticket);
         continue;
      }

      double candidate_sl = sl;
      if(g_cfg.breakeven_enable && profit >= g_cfg.breakeven_trigger_usd_001_lot * (volume / 0.01))
      {
         double be_dist = MoneyToPriceDistance(g_cfg.breakeven_offset_usd_001_lot, volume);
         candidate_sl = (type == POSITION_TYPE_BUY) ? open + be_dist : open - be_dist;
      }
      if(g_cfg.trailing_enable && profit >= g_cfg.trailing_start_usd_001_lot * (volume / 0.01))
      {
         double trail_dist = MoneyToPriceDistance(g_cfg.trailing_distance_usd_001_lot, volume);
         double trail_sl = (type == POSITION_TYPE_BUY) ? price - trail_dist : price + trail_dist;
         if(candidate_sl == 0.0 || (type == POSITION_TYPE_BUY && trail_sl > candidate_sl) || (type == POSITION_TYPE_SELL && trail_sl < candidate_sl))
            candidate_sl = trail_sl;
      }
      if(candidate_sl != sl && candidate_sl > 0.0)
         g_trade.PositionModify(ticket, NormalizeDouble(candidate_sl, _Digits), tp);
   }
}

int OnInit()
{
   LoadDashboardProfile();
   DrawDashboard();
   EventSetTimer(MathMax(1, InpTimerSeconds));
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   ObjectsDeleteAll(0, RP_PREFIX);
}

void OnTimer()
{
   LoadDashboardProfile();
   ManageOpenPositions();
   UpdateDashboardText();
}

void OnTick()
{
   ManageOpenPositions();
}

void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam)
{
   if(id != CHARTEVENT_OBJECT_CLICK) return;
   if(sparam == RP_PREFIX + "SAVE") SaveDashboardProfile();
   if(sparam == RP_PREFIX + "LOAD") { LoadDashboardProfile(); g_status = "reloaded json without recompiling"; }
   if(sparam == RP_PREFIX + "TOGGLE") g_cfg.enabled = !g_cfg.enabled;
   DrawDashboard();
}
//+------------------------------------------------------------------+
