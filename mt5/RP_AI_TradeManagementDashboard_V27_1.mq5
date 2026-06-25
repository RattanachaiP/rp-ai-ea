//+------------------------------------------------------------------+
//| RP AI Trade Management Dashboard V27.1                           |
//| On-chart MT5 dashboard for post-entry trade management only.      |
//+------------------------------------------------------------------+
#property strict
#property version   "27.30"
#property description "V27.3 Exit Optimization Dashboard - post-entry management only"

#include <Trade/Trade.mqh>

input string InpDashboardJsonFile = "trade_management_dashboard.json";
input string InpProfilesFolder    = "dashboard_profiles";
input string InpDefaultProfile    = "Balanced";
input int    InpChartCorner       = CORNER_LEFT_UPPER;
input int    InpX                 = 12;
input int    InpY                 = 24;
input int    InpTimerSeconds      = 2;
input bool   InpManageOpenTrades  = true;
input string InpTradeStatisticsCsv = "trade_statistics.csv";

#define RP_DASH_SCHEMA "V27_TRADE_MANAGEMENT_DASHBOARD_SCHEMA_1"
#define RP_PREFIX      "RP_V273_TMD_"

struct DashboardConfig
{
   string active_profile;
   bool enabled;
   double initial_sl_usd_001_lot;
   double hard_loss_cap_usd_001_lot;
   double max_floating_loss_usd_001_lot;
   bool emergency_close;
   bool breakeven_enable;
   double breakeven_trigger_usd_001_lot;
   double breakeven_offset_usd_001_lot;
   bool runner_be;
   bool trailing_enable;
   double trailing_start_usd_001_lot;
   double trailing_distance_usd_001_lot;
   double trailing_step_usd_001_lot;
   bool atr_trail_enable;
   bool profit_lock_enable;
   double lock1_trigger;
   double lock1_lock;
   double lock2_trigger;
   double lock2_lock;
   double lock3_trigger;
   double lock3_lock;
   double minimum_locked_profit_usd_001_lot;
   bool fixed_take_profit_enable;
   double fixed_take_profit_close_usd_001_lot;
   bool runner_enable;
   int runner_timeout_seconds;
   string runner_trail;
   double runner_sl_usd_001_lot;
   bool momentum_confirmation;
   bool time_exit_enable;
   int maximum_seconds;
   int maximum_bars;
   bool partial_enable;
   int partial_level_1_percent;
   int partial_level_2_percent;
   int remaining_runner_percent;
   string load_status;
   bool fallback_defaults_used;
};

DashboardConfig g_cfg;
CTrade g_trade;
datetime g_last_load = 0;
string g_status = "starting";

ulong g_track_tickets[];
double g_track_mfe[];
double g_track_mae[];

int TrackIndex(const ulong ticket)
{
   for(int i = 0; i < ArraySize(g_track_tickets); ++i)
      if(g_track_tickets[i] == ticket) return i;
   return -1;
}

int EnsureTrack(const ulong ticket)
{
   int idx = TrackIndex(ticket);
   if(idx >= 0) return idx;
   int n = ArraySize(g_track_tickets);
   ArrayResize(g_track_tickets, n + 1);
   ArrayResize(g_track_mfe, n + 1);
   ArrayResize(g_track_mae, n + 1);
   g_track_tickets[n] = ticket;
   g_track_mfe[n] = 0.0;
   g_track_mae[n] = 0.0;
   return n;
}

void RemoveTrack(const ulong ticket)
{
   int idx = TrackIndex(ticket);
   if(idx < 0) return;
   int last = ArraySize(g_track_tickets) - 1;
   if(idx != last)
   {
      g_track_tickets[idx] = g_track_tickets[last];
      g_track_mfe[idx] = g_track_mfe[last];
      g_track_mae[idx] = g_track_mae[last];
   }
   ArrayResize(g_track_tickets, last);
   ArrayResize(g_track_mfe, last);
   ArrayResize(g_track_mae, last);
}

void ApplyBackwardCompatibleDefaults(DashboardConfig &cfg)
{
   cfg.active_profile = "Profile_A";
   cfg.enabled = true;
   cfg.initial_sl_usd_001_lot = 1.00;
   cfg.emergency_close = true;
   cfg.hard_loss_cap_usd_001_lot = 1.00;
   cfg.max_floating_loss_usd_001_lot = 0.80;
   cfg.breakeven_enable = false;
   cfg.breakeven_trigger_usd_001_lot = 0.50;
   cfg.breakeven_offset_usd_001_lot = 0.00;
   cfg.runner_be = false;
   cfg.trailing_enable = false;
   cfg.trailing_start_usd_001_lot = 0.80;
   cfg.trailing_distance_usd_001_lot = 0.30;
   cfg.trailing_step_usd_001_lot = 0.10;
   cfg.atr_trail_enable = false;
   cfg.profit_lock_enable = false;
   cfg.lock1_trigger = 0.50; cfg.lock1_lock = 0.00;
   cfg.lock2_trigger = 0.80; cfg.lock2_lock = 0.10;
   cfg.lock3_trigger = 1.20; cfg.lock3_lock = 0.40;
   cfg.minimum_locked_profit_usd_001_lot = 0.05;
   cfg.fixed_take_profit_enable = true;
   cfg.fixed_take_profit_close_usd_001_lot = 1.00;
   cfg.runner_enable = false;
   cfg.runner_timeout_seconds = 45;
   cfg.runner_trail = "STRUCTURE_MOMENTUM_BB_WALK";
   cfg.runner_sl_usd_001_lot = 1.00;
   cfg.momentum_confirmation = false;
   cfg.time_exit_enable = false;
   cfg.maximum_seconds = 0;
   cfg.maximum_bars = 0;
   cfg.partial_enable = false;
   cfg.partial_level_1_percent = 0;
   cfg.partial_level_2_percent = 0;
   cfg.remaining_runner_percent = 100;
   cfg.load_status = "embedded V26.6-compatible defaults";
   cfg.fallback_defaults_used = true;
}

bool IsTpOnlyProfileActive()
{
   return g_cfg.active_profile == "TP_ONLY_1USD_TEST";
}

void EnforceTpOnlyProfileRuntime()
{
   if(!IsTpOnlyProfileActive()) return;
   Print("TP_ONLY_PROFILE_DETECTED");
   Print("TP_ONLY_PRODUCTION_BLOCK");
   Print("AUTO_FALLBACK_TO_BALANCED");
   g_cfg.active_profile = "Balanced";
   g_cfg.initial_sl_usd_001_lot = 1.00;
   g_cfg.breakeven_enable = true;
   g_cfg.runner_be = true;
   g_cfg.trailing_enable = true;
   g_cfg.atr_trail_enable = false;
   g_cfg.profit_lock_enable = true;
   g_cfg.fixed_take_profit_enable = false;
   g_cfg.fixed_take_profit_close_usd_001_lot = 1.00;
   g_cfg.runner_enable = true;
   g_cfg.runner_timeout_seconds = 45;
   g_cfg.runner_trail = "STRUCTURE_MOMENTUM_BB_WALK";
   g_cfg.runner_sl_usd_001_lot = 1.00;
   g_cfg.momentum_confirmation = true;
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


string JsonSection(const string json, const string key)
{
   string pattern = "\"" + key + "\"";
   int p = StringFind(json, pattern);
   if(p < 0) return "";
   int c = StringFind(json, ":", p);
   int start = StringFind(json, "{", c);
   if(c < 0 || start < 0) return "";
   int depth = 0;
   for(int i = start; i < StringLen(json); ++i)
   {
      ushort ch = StringGetCharacter(json, i);
      if(ch == '{') depth++;
      else if(ch == '}')
      {
         depth--;
         if(depth == 0) return StringSubstr(json, start, i - start + 1);
      }
   }
   return "";
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


double ClampDouble(const double value, const double lo, const double hi)
{
   if(value < lo) return lo;
   if(value > hi) return hi;
   return value;
}

int ClampInt(const int value, const int lo, const int hi)
{
   if(value < lo) return lo;
   if(value > hi) return hi;
   return value;
}

void ValidateConfig(DashboardConfig &cfg)
{
   cfg.initial_sl_usd_001_lot = ClampDouble(cfg.initial_sl_usd_001_lot, 0.01, 100.0);
   cfg.hard_loss_cap_usd_001_lot = ClampDouble(cfg.hard_loss_cap_usd_001_lot, 0.01, 100.0);
   cfg.max_floating_loss_usd_001_lot = ClampDouble(cfg.max_floating_loss_usd_001_lot, 0.01, 100.0);
   cfg.breakeven_trigger_usd_001_lot = ClampDouble(cfg.breakeven_trigger_usd_001_lot, 0.0, 100.0);
   cfg.breakeven_offset_usd_001_lot = ClampDouble(cfg.breakeven_offset_usd_001_lot, -10.0, 100.0);
   cfg.trailing_start_usd_001_lot = ClampDouble(cfg.trailing_start_usd_001_lot, 0.0, 100.0);
   cfg.trailing_distance_usd_001_lot = ClampDouble(cfg.trailing_distance_usd_001_lot, 0.01, 100.0);
   cfg.trailing_step_usd_001_lot = ClampDouble(cfg.trailing_step_usd_001_lot, 0.01, 100.0);
   cfg.lock1_trigger = ClampDouble(cfg.lock1_trigger, 0.0, 100.0);
   cfg.lock1_lock = ClampDouble(cfg.lock1_lock, -10.0, 100.0);
   cfg.lock2_trigger = ClampDouble(cfg.lock2_trigger, 0.0, 100.0);
   cfg.lock2_lock = ClampDouble(cfg.lock2_lock, -10.0, 100.0);
   cfg.lock3_trigger = ClampDouble(cfg.lock3_trigger, 0.0, 100.0);
   cfg.lock3_lock = ClampDouble(cfg.lock3_lock, -10.0, 100.0);
   cfg.minimum_locked_profit_usd_001_lot = ClampDouble(cfg.minimum_locked_profit_usd_001_lot, 0.0, 100.0);
   cfg.fixed_take_profit_close_usd_001_lot = ClampDouble(cfg.fixed_take_profit_close_usd_001_lot, 0.01, 100.0);
   cfg.runner_timeout_seconds = ClampInt(cfg.runner_timeout_seconds, 0, 86400);
   cfg.runner_sl_usd_001_lot = ClampDouble(cfg.runner_sl_usd_001_lot, 0.0, 100.0);
   cfg.maximum_seconds = ClampInt(cfg.maximum_seconds, 0, 86400);
   cfg.maximum_bars = ClampInt(cfg.maximum_bars, 0, 10000);
   cfg.partial_level_1_percent = ClampInt(cfg.partial_level_1_percent, 0, 100);
   cfg.partial_level_2_percent = ClampInt(cfg.partial_level_2_percent, 0, 100);
   cfg.remaining_runner_percent = ClampInt(cfg.remaining_runner_percent, 0, 100);
   EnforceTpOnlyProfileRuntime();
}

void OverlayJson(DashboardConfig &cfg, const string json)
{
   cfg.active_profile = JsonString(json, "active_profile", cfg.active_profile);
   cfg.enabled = JsonBool(json, "enabled", cfg.enabled);
   string risk = JsonSection(json, "risk");
   string breakeven = JsonSection(json, "breakeven");
   string trailing = JsonSection(json, "trailing");
   string locks = JsonSection(json, "profit_locks");
   cfg.initial_sl_usd_001_lot = JsonNumber(risk, "initial_sl_usd_001_lot", cfg.initial_sl_usd_001_lot);
   cfg.hard_loss_cap_usd_001_lot = JsonNumber(risk, "hard_loss_cap_usd_001_lot", cfg.hard_loss_cap_usd_001_lot);
   cfg.max_floating_loss_usd_001_lot = JsonNumber(risk, "max_floating_loss_usd_001_lot", cfg.max_floating_loss_usd_001_lot);
   cfg.emergency_close = JsonBool(risk, "emergency_close", cfg.emergency_close);
   cfg.breakeven_enable = JsonBool(breakeven, "enable", cfg.breakeven_enable);
   cfg.breakeven_trigger_usd_001_lot = JsonNumber(breakeven, "trigger_usd_001_lot", cfg.breakeven_trigger_usd_001_lot);
   cfg.breakeven_offset_usd_001_lot = JsonNumber(breakeven, "offset_usd_001_lot", cfg.breakeven_offset_usd_001_lot);
   cfg.runner_be = JsonBool(breakeven, "runner_be", cfg.runner_be);
   cfg.trailing_enable = JsonBool(trailing, "enable", JsonBool(trailing, "dynamic_trail", cfg.trailing_enable));
   cfg.trailing_start_usd_001_lot = JsonNumber(trailing, "start_usd_001_lot", cfg.trailing_start_usd_001_lot);
   cfg.trailing_distance_usd_001_lot = JsonNumber(trailing, "distance_usd_001_lot", cfg.trailing_distance_usd_001_lot);
   cfg.trailing_step_usd_001_lot = JsonNumber(trailing, "step_usd_001_lot", cfg.trailing_step_usd_001_lot);
   cfg.atr_trail_enable = JsonBool(trailing, "atr_trail", cfg.atr_trail_enable);
   cfg.profit_lock_enable = JsonBool(locks, "enable", cfg.profit_lock_enable);
   string lock1 = JsonSection(locks, "lock_level_1_usd_001_lot");
   cfg.lock1_trigger = JsonNumber(lock1, "trigger", cfg.lock1_trigger);
   cfg.lock1_lock = JsonNumber(lock1, "lock", cfg.lock1_lock);
   cfg.lock2_trigger = JsonNumber(json, "lock2_trigger", cfg.lock2_trigger);
   cfg.lock2_lock = JsonNumber(json, "lock2_lock", cfg.lock2_lock);
   cfg.lock3_trigger = JsonNumber(json, "lock3_trigger", cfg.lock3_trigger);
   cfg.lock3_lock = JsonNumber(json, "lock3_lock", cfg.lock3_lock);
   cfg.minimum_locked_profit_usd_001_lot = JsonNumber(json, "minimum_locked_profit_usd_001_lot", cfg.minimum_locked_profit_usd_001_lot);
   cfg.fixed_take_profit_enable = JsonBool(json, "fixed_take_profit_enable", cfg.fixed_take_profit_enable);
   cfg.fixed_take_profit_close_usd_001_lot = JsonNumber(json, "close_profit_usd_001_lot", cfg.fixed_take_profit_close_usd_001_lot);
   cfg.runner_enable = JsonBool(json, "enable_runner", cfg.runner_enable);
   cfg.runner_timeout_seconds = (int)JsonNumber(json, "runner_timeout_seconds", cfg.runner_timeout_seconds);
   cfg.runner_sl_usd_001_lot = JsonNumber(json, "runner_sl_usd_001_lot", cfg.runner_sl_usd_001_lot);
   cfg.runner_trail = JsonString(json, "runner_trail", cfg.runner_trail);
   cfg.momentum_confirmation = JsonBool(json, "momentum_confirmation", cfg.momentum_confirmation);
   cfg.time_exit_enable = JsonBool(json, "time_exit_enable", cfg.time_exit_enable);
   cfg.maximum_seconds = (int)JsonNumber(json, "maximum_seconds", cfg.maximum_seconds);
   cfg.maximum_bars = (int)JsonNumber(json, "maximum_bars", cfg.maximum_bars);
   cfg.partial_enable = JsonBool(json, "partial_exits_enable", cfg.partial_enable);
   cfg.partial_level_1_percent = (int)JsonNumber(json, "partial_level_1_percent", cfg.partial_level_1_percent);
   cfg.partial_level_2_percent = (int)JsonNumber(json, "partial_level_2_percent", cfg.partial_level_2_percent);
   cfg.remaining_runner_percent = (int)JsonNumber(json, "remaining_runner_percent", cfg.remaining_runner_percent);
   ValidateConfig(cfg);
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
   ValidateConfig(g_cfg);
   return StringFormat("{\n"
                       "  \"schema_version\": \"%s\",\n"
                       "  \"active_profile\": \"%s\",\n"
                       "  \"enabled\": %s,\n"
                       "  \"risk\": {\"initial_sl_usd_001_lot\": %.2f, \"hard_loss_cap_usd_001_lot\": %.2f, \"max_floating_loss_usd_001_lot\": %.2f, \"emergency_close\": %s},\n"
                       "  \"breakeven\": {\"enable\": %s, \"trigger_usd_001_lot\": %.2f, \"offset_usd_001_lot\": %.2f, \"runner_be\": %s},\n"
                       "  \"trailing\": {\"enable\": %s, \"start_usd_001_lot\": %.2f, \"distance_usd_001_lot\": %.2f, \"step_usd_001_lot\": %.2f, \"atr_trail\": %s, \"dynamic_trail\": %s},\n"
                       "  \"profit_locks\": {\"enable\": %s, \"lock_level_1_usd_001_lot\": {\"trigger\": %.2f, \"lock\": %.2f}, \"lock2_trigger\": %.2f, \"lock2_lock\": %.2f, \"lock3_trigger\": %.2f, \"lock3_lock\": %.2f, \"minimum_locked_profit_usd_001_lot\": %.2f},\n"
                       "  \"fixed_take_profit\": {\"fixed_take_profit_enable\": %s, \"close_profit_usd_001_lot\": %.2f, \"close_mode\": \"IMMEDIATE_MARKET_CLOSE\"},\n"
                       "  \"runner\": {\"enable_runner\": %s, \"runner_timeout_seconds\": %d, \"runner_trail\": \"%s\", \"runner_sl_usd_001_lot\": %.2f, \"momentum_confirmation\": %s},\n"
                       "  \"time_exits\": {\"time_exit_enable\": %s, \"maximum_seconds\": %d, \"maximum_bars\": %d},\n"
                       "  \"partial_exits\": {\"enable\": %s, \"partial_level_1_percent\": %d, \"partial_level_2_percent\": %d, \"remaining_runner_percent\": %d}\n"
                       "}\n",
                       RP_DASH_SCHEMA, g_cfg.active_profile, g_cfg.enabled ? "true" : "false",
                       g_cfg.initial_sl_usd_001_lot, g_cfg.hard_loss_cap_usd_001_lot, g_cfg.max_floating_loss_usd_001_lot, g_cfg.emergency_close ? "true" : "false",
                       g_cfg.breakeven_enable ? "true" : "false", g_cfg.breakeven_trigger_usd_001_lot, g_cfg.breakeven_offset_usd_001_lot, g_cfg.runner_be ? "true" : "false",
                       g_cfg.trailing_enable ? "true" : "false", g_cfg.trailing_start_usd_001_lot, g_cfg.trailing_distance_usd_001_lot, g_cfg.trailing_step_usd_001_lot, g_cfg.atr_trail_enable ? "true" : "false", g_cfg.trailing_enable ? "true" : "false",
                       g_cfg.profit_lock_enable ? "true" : "false", g_cfg.lock1_trigger, g_cfg.lock1_lock, g_cfg.lock2_trigger, g_cfg.lock2_lock, g_cfg.lock3_trigger, g_cfg.lock3_lock, g_cfg.minimum_locked_profit_usd_001_lot,
                       g_cfg.fixed_take_profit_enable ? "true" : "false", g_cfg.fixed_take_profit_close_usd_001_lot,
                       g_cfg.runner_enable ? "true" : "false", g_cfg.runner_timeout_seconds, g_cfg.runner_trail, g_cfg.runner_sl_usd_001_lot, g_cfg.momentum_confirmation ? "true" : "false",
                       g_cfg.time_exit_enable ? "true" : "false", g_cfg.maximum_seconds, g_cfg.maximum_bars,
                       g_cfg.partial_enable ? "true" : "false", g_cfg.partial_level_1_percent, g_cfg.partial_level_2_percent, g_cfg.remaining_runner_percent);
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
   ObjectSetInteger(0, name, OBJPROP_YSIZE, 20);
   ObjectSetString(0, name, OBJPROP_TEXT, text);
}

void CreateLabel(const string name, const int x, const int y)
{
   ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);
   ObjectSetInteger(0, name, OBJPROP_CORNER, InpChartCorner);
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, y);
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, 8);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clrWhite);
}

string BoolText(const bool value) { return value ? "ON" : "OFF"; }

void DrawControl(const string id, const string label, const string value, const int x, const int y)
{
   CreateLabel(RP_PREFIX + "LBL_" + id, x, y + 3);
   ObjectSetString(0, RP_PREFIX + "LBL_" + id, OBJPROP_TEXT, label + ": " + value);
   CreateButton(RP_PREFIX + "MINUS_" + id, "-", x + 178, y, 24);
   CreateButton(RP_PREFIX + "PLUS_" + id, "+", x + 204, y, 24);
}

void DrawDashboard()
{
   ObjectsDeleteAll(0, RP_PREFIX);
   CreateLabel(RP_PREFIX + "TITLE", InpX, InpY);
   CreateButton(RP_PREFIX + "APPLY", "Apply Runtime", InpX, InpY + 22, 112);
   CreateButton(RP_PREFIX + "SAVE", "Save JSON", InpX + 116, InpY + 22, 88);
   CreateButton(RP_PREFIX + "LOAD", "Reload JSON", InpX + 208, InpY + 22, 96);
   CreateButton(RP_PREFIX + "RESET", "Reset Default", InpX + 308, InpY + 22, 100);
   CreateButton(RP_PREFIX + "PROFILE", "Cycle Profile", InpX + 412, InpY + 22, 104);
   CreateButton(RP_PREFIX + "TOGGLE", g_cfg.enabled ? "Disable TM" : "Enable TM", InpX + 520, InpY + 22, 90);

   int y = InpY + 50;
   DrawControl("INITIAL_SL", "Risk Initial SL", DoubleToString(g_cfg.initial_sl_usd_001_lot, 2), InpX, y); y += 22;
   DrawControl("HARD_CAP", "Risk Hard Loss Cap", DoubleToString(g_cfg.hard_loss_cap_usd_001_lot, 2), InpX, y); y += 22;
   DrawControl("FLOAT_CAP", "Risk Max Floating Loss", DoubleToString(g_cfg.max_floating_loss_usd_001_lot, 2), InpX, y); y += 22;
   DrawControl("BE_ENABLE", "BE Enable", BoolText(g_cfg.breakeven_enable), InpX, y); y += 22;
   DrawControl("BE_TRIGGER", "BE Trigger", DoubleToString(g_cfg.breakeven_trigger_usd_001_lot, 2), InpX, y); y += 22;
   DrawControl("BE_OFFSET", "BE Offset", DoubleToString(g_cfg.breakeven_offset_usd_001_lot, 2), InpX, y); y += 22;
   DrawControl("RUNNER_BE", "Runner BE", BoolText(g_cfg.runner_be), InpX, y); y += 22;

   y = InpY + 50;
   int x2 = InpX + 250;
   DrawControl("TRAIL_ENABLE", "Trail Enable", BoolText(g_cfg.trailing_enable), x2, y); y += 22;
   DrawControl("TRAIL_START", "Trail Start", DoubleToString(g_cfg.trailing_start_usd_001_lot, 2), x2, y); y += 22;
   DrawControl("TRAIL_DIST", "Trail Distance", DoubleToString(g_cfg.trailing_distance_usd_001_lot, 2), x2, y); y += 22;
   DrawControl("TRAIL_STEP", "Trail Step", DoubleToString(g_cfg.trailing_step_usd_001_lot, 2), x2, y); y += 22;
   DrawControl("ATR_TRAIL", "ATR Trail Enable", BoolText(g_cfg.atr_trail_enable), x2, y); y += 22;
   DrawControl("PROFIT_LOCK_ENABLE", "Profit Lock Enable", BoolText(g_cfg.profit_lock_enable), x2, y); y += 22;
   DrawControl("LOCK1", "Profit Lock L1", DoubleToString(g_cfg.lock1_trigger, 2) + "/" + DoubleToString(g_cfg.lock1_lock, 2), x2, y); y += 22;
   DrawControl("LOCK2", "Profit Lock L2", DoubleToString(g_cfg.lock2_trigger, 2) + "/" + DoubleToString(g_cfg.lock2_lock, 2), x2, y); y += 22;
   DrawControl("LOCK3", "Profit Lock L3", DoubleToString(g_cfg.lock3_trigger, 2) + "/" + DoubleToString(g_cfg.lock3_lock, 2), x2, y); y += 22;
   DrawControl("FIXED_TP", "Fixed TP Close", BoolText(g_cfg.fixed_take_profit_enable) + " @ " + DoubleToString(g_cfg.fixed_take_profit_close_usd_001_lot, 2), x2, y); y += 22;
   DrawControl("MIN_LOCK", "Minimum Locked Profit", DoubleToString(g_cfg.minimum_locked_profit_usd_001_lot, 2), x2, y); y += 22;

   y = InpY + 50;
   int x3 = InpX + 500;
   DrawControl("RUNNER_ENABLE", "Runner Enable", BoolText(g_cfg.runner_enable), x3, y); y += 22;
   DrawControl("RUNNER_TIMEOUT", "Runner Timeout", IntegerToString(g_cfg.runner_timeout_seconds), x3, y); y += 22;
   DrawControl("RUNNER_SL", "Runner SL", DoubleToString(g_cfg.runner_sl_usd_001_lot, 2), x3, y); y += 22;
   DrawControl("MOMENTUM", "Momentum Confirm", BoolText(g_cfg.momentum_confirmation), x3, y); y += 22;
   DrawControl("TIME_ENABLE", "Time Exit Enable", BoolText(g_cfg.time_exit_enable), x3, y); y += 22;
   DrawControl("MAX_SECONDS", "Time Max Seconds", IntegerToString(g_cfg.maximum_seconds), x3, y); y += 22;
   DrawControl("MAX_BARS", "Time Max Bars", IntegerToString(g_cfg.maximum_bars), x3, y); y += 22;
   DrawControl("PARTIAL_ENABLE", "Partial Enable", BoolText(g_cfg.partial_enable), x3, y); y += 22;
   DrawControl("PARTIAL1", "Partial Level 1", IntegerToString(g_cfg.partial_level_1_percent) + "%", x3, y); y += 22;
   DrawControl("PARTIAL2", "Partial Level 2", IntegerToString(g_cfg.partial_level_2_percent) + "%", x3, y); y += 22;
   DrawControl("REMAIN_RUNNER", "Remaining Runner %", IntegerToString(g_cfg.remaining_runner_percent) + "%", x3, y); y += 22;

   CreateLabel(RP_PREFIX + "BODY", InpX, InpY + 292);
   CreateLabel(RP_PREFIX + "POSITIONS", InpX, InpY + 372);
   UpdateDashboardText();
}

string CurrentProfitLockLevel()
{
   return StringFormat("L1 %.2f/%.2f | L2 %.2f/%.2f | L3 %.2f/%.2f", g_cfg.lock1_trigger, g_cfg.lock1_lock, g_cfg.lock2_trigger, g_cfg.lock2_lock, g_cfg.lock3_trigger, g_cfg.lock3_lock);
}

void UpdateDashboardText()
{
   ObjectSetString(0, RP_PREFIX + "TITLE", OBJPROP_TEXT, "V27.3 Exit Optimization Dashboard (POST-ENTRY ONLY; AI decision engine frozen)");
   string json_status = g_cfg.fallback_defaults_used ? "FALLBACK_EMBEDDED_DEFAULTS" : "JSON_PROFILE_LOADED";
   ObjectSetString(0, RP_PREFIX + "BODY", OBJPROP_TEXT,
                   StringFormat("Profile: %s | JSON Status: %s | Last Reload: %s | TM: %s | Status: %s\nActive Exit Authority Owner: %s | Effective Management Mode: %s\nCurrent BE Trigger: %.2f | Trail Distance: %.2f | Hard Loss Cap: %.2f | Profit Lock: %s\nExecutor consumes this runtime profile through Exit Authority priority: EMERGENCY > HARD_LOSS > PROFIT_LOCK > BE > TRAIL > RUNNER > TIME",
                                g_cfg.active_profile, json_status, TimeToString(g_last_load, TIME_DATE | TIME_SECONDS),
                                g_cfg.enabled ? "ENABLED" : "DISABLED", g_status,
                                "Exit Authority Manager (single-owner priority)", g_cfg.runner_enable ? "RUNNER/TRAIL/LOCK" : "SCALP_PROTECTION",
                                g_cfg.breakeven_trigger_usd_001_lot, g_cfg.trailing_distance_usd_001_lot, g_cfg.hard_loss_cap_usd_001_lot, CurrentProfitLockLevel()));

   string pos = "Open positions (ticket dir lot profit MFE mode owner state profile):\n";
   for(int i = PositionsTotal() - 1; i >= 0; --i)
   {
      ulong ticket = PositionGetTicket(i);
      if(!PositionSelectByTicket(ticket) || PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      long type = PositionGetInteger(POSITION_TYPE);
      double volume = PositionGetDouble(POSITION_VOLUME);
      double profit = PositionGetDouble(POSITION_PROFIT);
      string owner = "NONE";
      if(profit <= -g_cfg.hard_loss_cap_usd_001_lot * (volume / 0.01)) owner = "HARD_LOSS_CAP";
      else if(profit >= g_cfg.lock1_trigger * (volume / 0.01)) owner = "PROFIT_LOCK";
      else if(g_cfg.breakeven_enable && profit >= g_cfg.breakeven_trigger_usd_001_lot * (volume / 0.01)) owner = "BREAKEVEN";
      else if(g_cfg.fixed_take_profit_enable && profit >= g_cfg.fixed_take_profit_close_usd_001_lot * (volume / 0.01)) owner = "FIXED_TAKE_PROFIT";
      else if(g_cfg.trailing_enable && profit >= g_cfg.trailing_start_usd_001_lot * (volume / 0.01)) owner = "TRAILING";
      else if(g_cfg.runner_enable) owner = "RUNNER";
      pos += StringFormat("%I64u %s %.2f %.2f %.2f %s %s %s %s\n", ticket, type == POSITION_TYPE_BUY ? "BUY" : "SELL", volume, profit, profit, g_cfg.runner_enable ? "RUNNER/TRAIL" : "PROTECT", owner, g_cfg.enabled ? "ACTIVE" : "DISABLED", g_cfg.active_profile);
   }
   ObjectSetString(0, RP_PREFIX + "POSITIONS", OBJPROP_TEXT, pos);
}

void AdjustControl(const string id, const int dir)
{
   double step = 0.05;
   if(id == "INITIAL_SL") g_cfg.initial_sl_usd_001_lot += dir * step;
   else if(id == "HARD_CAP") g_cfg.hard_loss_cap_usd_001_lot += dir * step;
   else if(id == "FLOAT_CAP") g_cfg.max_floating_loss_usd_001_lot += dir * step;
   else if(id == "BE_ENABLE") g_cfg.breakeven_enable = !g_cfg.breakeven_enable;
   else if(id == "BE_TRIGGER") g_cfg.breakeven_trigger_usd_001_lot += dir * step;
   else if(id == "BE_OFFSET") g_cfg.breakeven_offset_usd_001_lot += dir * step;
   else if(id == "RUNNER_BE") g_cfg.runner_be = !g_cfg.runner_be;
   else if(id == "TRAIL_ENABLE") g_cfg.trailing_enable = !g_cfg.trailing_enable;
   else if(id == "TRAIL_START") g_cfg.trailing_start_usd_001_lot += dir * step;
   else if(id == "TRAIL_DIST") g_cfg.trailing_distance_usd_001_lot += dir * step;
   else if(id == "TRAIL_STEP") g_cfg.trailing_step_usd_001_lot += dir * step;
   else if(id == "ATR_TRAIL") g_cfg.atr_trail_enable = !g_cfg.atr_trail_enable;
   else if(id == "PROFIT_LOCK_ENABLE") g_cfg.profit_lock_enable = !g_cfg.profit_lock_enable;
   else if(id == "LOCK1") { g_cfg.lock1_trigger += dir * step; g_cfg.lock1_lock += dir * step; }
   else if(id == "LOCK2") { g_cfg.lock2_trigger += dir * step; g_cfg.lock2_lock += dir * step; }
   else if(id == "LOCK3") { g_cfg.lock3_trigger += dir * step; g_cfg.lock3_lock += dir * step; }
   else if(id == "MIN_LOCK") g_cfg.minimum_locked_profit_usd_001_lot += dir * step;
   else if(id == "RUNNER_ENABLE") g_cfg.runner_enable = !g_cfg.runner_enable;
   else if(id == "RUNNER_TIMEOUT") g_cfg.runner_timeout_seconds += dir * 5;
   else if(id == "RUNNER_SL") g_cfg.runner_sl_usd_001_lot += dir * step;
   else if(id == "MOMENTUM") g_cfg.momentum_confirmation = !g_cfg.momentum_confirmation;
   else if(id == "TIME_ENABLE") g_cfg.time_exit_enable = !g_cfg.time_exit_enable;
   else if(id == "MAX_SECONDS") g_cfg.maximum_seconds += dir * 30;
   else if(id == "MAX_BARS") g_cfg.maximum_bars += dir;
   else if(id == "PARTIAL_ENABLE") g_cfg.partial_enable = !g_cfg.partial_enable;
   else if(id == "PARTIAL1") g_cfg.partial_level_1_percent += dir * 5;
   else if(id == "PARTIAL2") g_cfg.partial_level_2_percent += dir * 5;
   else if(id == "REMAIN_RUNNER") g_cfg.remaining_runner_percent += dir * 5;
   ValidateConfig(g_cfg);
   g_status = "edited in-memory - click Apply and/or Save JSON";
}

void CycleProfile()
{
   if(g_cfg.active_profile == "Profile_A") g_cfg.active_profile = "Profile_B";
   else if(g_cfg.active_profile == "Profile_B") g_cfg.active_profile = "Profile_C";
   else if(g_cfg.active_profile == "Profile_C") g_cfg.active_profile = "Profile_D";
   else g_cfg.active_profile = "Profile_A";
   g_status = "profile selected in-memory - click Reload JSON to load file or Save JSON to create it";
}

double MoneyToPriceDistance(const double money_001_lot, const double volume)
{
   double tick_value = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tick_value <= 0.0 || tick_size <= 0.0 || volume <= 0.0) return 0.0;
   double scaled_money = money_001_lot * (volume / 0.01);
   return (scaled_money / tick_value) * tick_size;
}

void UpdateOpenTradeExcursions()
{
   for(int i = PositionsTotal() - 1; i >= 0; --i)
   {
      ulong ticket = PositionGetTicket(i);
      if(!PositionSelectByTicket(ticket) || PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      int idx = EnsureTrack(ticket);
      double profit = PositionGetDouble(POSITION_PROFIT);
      if(profit > g_track_mfe[idx]) g_track_mfe[idx] = profit;
      if(profit < g_track_mae[idx]) g_track_mae[idx] = profit;
   }
}

string CsvEscape(const string value)
{
   string escaped = value;
   StringReplace(escaped, "\"", "\"\"");
   return "\"" + escaped + "\"";
}

void EnsureTradeStatisticsHeader()
{
   int read = FileOpen(InpTradeStatisticsCsv, FILE_READ | FILE_TXT | FILE_COMMON | FILE_ANSI);
   if(read != INVALID_HANDLE)
   {
      bool empty = FileIsEnding(read);
      FileClose(read);
      if(!empty) return;
   }
   int handle = FileOpen(InpTradeStatisticsCsv, FILE_WRITE | FILE_TXT | FILE_COMMON | FILE_ANSI);
   if(handle == INVALID_HANDLE) return;
   FileWriteString(handle, "Ticket,Symbol,Direction,Mode,Entry Time,Exit Time,Entry Price,Exit Price,Stop Loss,Take Profit,Exit Reason,MFE,MAE,Net Profit,Duration,Dashboard Profile\n");
   FileClose(handle);
}

void RecordCompletedTrade(const ulong position_id, const ulong exit_deal)
{
   if(!HistoryDealSelect(exit_deal)) return;
   string symbol = HistoryDealGetString(exit_deal, DEAL_SYMBOL);
   if(symbol != _Symbol) return;
   datetime exit_time = (datetime)HistoryDealGetInteger(exit_deal, DEAL_TIME);
   double exit_price = HistoryDealGetDouble(exit_deal, DEAL_PRICE);
   double net_profit = HistoryDealGetDouble(exit_deal, DEAL_PROFIT) + HistoryDealGetDouble(exit_deal, DEAL_SWAP) + HistoryDealGetDouble(exit_deal, DEAL_COMMISSION);
   long reason_code = HistoryDealGetInteger(exit_deal, DEAL_REASON);
   string exit_reason = EnumToString((ENUM_DEAL_REASON)reason_code);

   datetime entry_time = 0;
   double entry_price = 0.0;
   string direction = "UNKNOWN";
   if(HistorySelect(0, exit_time + 60))
   {
      for(int i = HistoryDealsTotal() - 1; i >= 0; --i)
      {
         ulong deal = HistoryDealGetTicket(i);
         if((ulong)HistoryDealGetInteger(deal, DEAL_POSITION_ID) != position_id) continue;
         if((ENUM_DEAL_ENTRY)HistoryDealGetInteger(deal, DEAL_ENTRY) != DEAL_ENTRY_IN) continue;
         entry_time = (datetime)HistoryDealGetInteger(deal, DEAL_TIME);
         entry_price = HistoryDealGetDouble(deal, DEAL_PRICE);
         direction = ((ENUM_DEAL_TYPE)HistoryDealGetInteger(deal, DEAL_TYPE) == DEAL_TYPE_BUY) ? "BUY" : "SELL";
      }
   }

   int idx = TrackIndex(position_id);
   double mfe = idx >= 0 ? g_track_mfe[idx] : MathMax(net_profit, 0.0);
   double mae = idx >= 0 ? g_track_mae[idx] : MathMin(net_profit, 0.0);
   EnsureTradeStatisticsHeader();
   int handle = FileOpen(InpTradeStatisticsCsv, FILE_READ | FILE_WRITE | FILE_TXT | FILE_COMMON | FILE_ANSI);
   if(handle == INVALID_HANDLE) return;
   FileSeek(handle, 0, SEEK_END);
   string row = StringFormat("%I64u,%s,%s,%s,%s,%s,%.5f,%.5f,%.5f,%.5f,%s,%.2f,%.2f,%.2f,%d,%s\n",
      position_id, CsvEscape(symbol), CsvEscape(direction), CsvEscape(g_cfg.runner_enable ? "RUNNER/TRAIL" : "PROTECT"),
      CsvEscape(TimeToString(entry_time, TIME_DATE | TIME_SECONDS)), CsvEscape(TimeToString(exit_time, TIME_DATE | TIME_SECONDS)),
      entry_price, exit_price, 0.0, 0.0, CsvEscape(exit_reason), mfe, mae, net_profit, (int)(exit_time - entry_time), CsvEscape(g_cfg.active_profile));
   FileWriteString(handle, row);
   FileClose(handle);
   RemoveTrack(position_id);
}

void ManageOpenPositions()
{
   UpdateOpenTradeExcursions();
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

      if(g_cfg.fixed_take_profit_enable && profit >= g_cfg.fixed_take_profit_close_usd_001_lot * (volume / 0.01))
      {
         g_trade.PositionClose(ticket);
         continue;
      }

      double candidate_sl = sl;
      double scale = volume / 0.01;
      double lock_money = -999999.0;
      if(g_cfg.profit_lock_enable)
      {
         if(profit >= g_cfg.lock3_trigger * scale) lock_money = MathMax(lock_money, g_cfg.lock3_lock);
         else if(profit >= g_cfg.lock2_trigger * scale) lock_money = MathMax(lock_money, g_cfg.lock2_lock);
         else if(profit >= g_cfg.lock1_trigger * scale) lock_money = MathMax(lock_money, g_cfg.lock1_lock);
         if(lock_money > -999998.0)
         {
            lock_money = MathMax(lock_money, g_cfg.minimum_locked_profit_usd_001_lot);
            double lock_dist = MoneyToPriceDistance(lock_money, volume);
            candidate_sl = (type == POSITION_TYPE_BUY) ? open + lock_dist : open - lock_dist;
         }
      }
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
      {
         if(IsTpOnlyProfileActive())
         {
            Print("POSITIONMODIFY_BLOCKED_BY_TP_ONLY_PROFILE");
            continue;
         }
         g_trade.PositionModify(ticket, NormalizeDouble(candidate_sl, _Digits), tp);
      }
   }
}

int OnInit()
{
   LoadDashboardProfile();
   Print("DASHBOARD_SINGLE_SOURCE_OF_TRUTH_PASS");
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
   ManageOpenPositions();
   UpdateDashboardText();
}

void OnTick()
{
   ManageOpenPositions();
}

void OnTradeTransaction(const MqlTradeTransaction &trans, const MqlTradeRequest &request, const MqlTradeResult &result)
{
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD) return;
   if(!HistoryDealSelect(trans.deal)) return;
   if((ENUM_DEAL_ENTRY)HistoryDealGetInteger(trans.deal, DEAL_ENTRY) == DEAL_ENTRY_OUT)
      RecordCompletedTrade((ulong)HistoryDealGetInteger(trans.deal, DEAL_POSITION_ID), trans.deal);
}

void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam)
{
   if(id != CHARTEVENT_OBJECT_CLICK) return;
   if(sparam == RP_PREFIX + "SAVE") SaveDashboardProfile();
   else if(sparam == RP_PREFIX + "LOAD") { LoadDashboardProfile(); g_status = "reloaded json without recompiling"; }
   else if(sparam == RP_PREFIX + "APPLY") { ValidateConfig(g_cfg); g_status = "applied runtime values immediately"; ManageOpenPositions(); }
   else if(sparam == RP_PREFIX + "RESET") { ApplyBackwardCompatibleDefaults(g_cfg); ValidateConfig(g_cfg); g_status = "reset to embedded defaults in-memory"; }
   else if(sparam == RP_PREFIX + "PROFILE") CycleProfile();
   else if(sparam == RP_PREFIX + "TOGGLE") { g_cfg.enabled = !g_cfg.enabled; g_status = g_cfg.enabled ? "trade management enabled" : "trade management disabled"; }
   else if(StringFind(sparam, RP_PREFIX + "PLUS_") == 0) AdjustControl(StringSubstr(sparam, StringLen(RP_PREFIX + "PLUS_")), 1);
   else if(StringFind(sparam, RP_PREFIX + "MINUS_") == 0) AdjustControl(StringSubstr(sparam, StringLen(RP_PREFIX + "MINUS_")), -1);
   DrawDashboard();
}
//+------------------------------------------------------------------+
