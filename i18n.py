"""Lightweight two-locale translation layer for the Tariff Advisor demo.

Locales: ``az`` (default) and ``en``. Every user-visible string lives here as
a key/EN/AZ triple so both languages stay in sync. Data-derived sentences
(recommendation explanations, admin reason texts, notification bodies) are
rendered at display time with :func:`translate`, so switching the language
re-renders them too.

No third-party dependency: plain dicts + ``str.format``.
"""

from __future__ import annotations

from config import Config  # noqa: F401  (kept for symmetry with app config)

LOCALES = ("az", "en")
DEFAULT_LOCALE = "az"

_EN: dict[str, str] = {}
_AZ: dict[str, str] = {}


def _p(key: str, en: str, az: str) -> None:
    _EN[key] = en
    _AZ[key] = az


# --------------------------------------------------------------------------- #
# common chrome
# --------------------------------------------------------------------------- #
_p("lang.aria", "Language", "Dil")
_p("demo.strip", "Demo mode · synthetic data — not live Bakcell data",
   "Demo rejimi · süni məlumatlar — canlı Bakcell məlumatları deyil")
_p("demo.strip_admin",
   "Demo mode · synthetic sample data — never presented as live Bakcell data",
   "Demo rejimi · süni nümunə məlumatları — heç vaxt canlı Bakcell məlumatı kimi təqdim olunmur")
_p("footer.note", "Estimates only — no saving is guaranteed. Synthetic demo data.",
   "Yalnız təxminlər — heç bir qənaət zəmanətli deyil. Süni demo məlumatlar.")
_p("nav.home", "Home", "Ana səhifə")
_p("nav.tariffs", "Tariffs", "Tariflər")
_p("nav.history", "History", "Tarixçə")
_p("nav.alerts", "Alerts", "Xəbərdarlıqlar")
_p("a11y.home", "Tariff Advisor home", "Tariff Advisor ana səhifəsi")
_p("a11y.notifications", "Notifications", "Bildirişlər")
_p("a11y.signout", "Sign out", "Çıxış")

_p("common.unknown", "unknown", "məlum deyil")
_p("common.unavailable", "Unavailable", "Əlçatmaz")
_p("common.partial_unavailable", "Partially unavailable", "Qismən əlçatmaz")
_p("common.not_in_source", "Not in source data", "Mənbə məlumatlarında yoxdur")
_p("common.missing_in_source", "missing in source", "mənbədə yoxdur")
_p("common.no_snapshot", "no snapshot", "anlıq görüntü yoxdur")
_p("common.over", "over", "artıq")
_p("common.no_rows", "no usage rows", "istifadə sətiri yoxdur")

_p("unit.per_month", "/ month", "/ ay")
_p("unit.gb_month", "GB / month", "GB / ay")
_p("unit.min_month", "min. / month", "dəq. / ay")
_p("unit.sms_month", "SMS / month", "SMS / ay")
_p("unit.azn_mo", "AZN/mo", "AZN/ay")
_p("unit.azn_spend", "AZN spend", "AZN xərc")
_p("unit.pct_data", "% data", "% data")
_p("unit.pct_minutes", "% minutes", "% dəqiqə")

_p("action.switch", "Switch", "Keç")
_p("action.switch_to", "Switch to {name}", "{name} planına keç")
_p("action.switch_confirm", "Switch your tariff to {name}?",
   "{name} tarifinə keçəkmi?")
_p("action.in_use", "In use", "İstifadədə")
_p("action.mark_read", "Mark read", "Oxunub et")
_p("action.keep", "keep", "saxla")
_p("action.detail", "Detail", "Ətraflı")
_p("action.prev", "← Previous", "← Əvvəlki")
_p("action.next", "Next →", "Növbəti →")
_p("action.apply", "Apply", "Tətbiq et")
_p("action.filter", "Filter", "Filtr")
_p("action.reset", "Reset", "Sıfırla")
_p("pager.page", "Page {p} / {P}", "Səhifə {p} / {P}")

_p("filter.from", "From month", "Başlanğıc ayı")
_p("filter.to", "To month", "Son ayı")
_p("filter.tariff", "Tariff", "Tarif")
_p("filter.all_tariffs", "All tariffs", "Bütün tariflər")
_p("filter.search_id", "Search customer ID", "Müştəri ID axtar")

_p("pill.best_keep", "Best match · keep your plan",
   "Ən uyğun · planınızı saxlayın")
_p("pill.top", "Top suggestion", "Ən yaxşı təklif")
_p("pill.current", "Current", "Cari")
_p("pill.your_current", "Your current plan", "Sizin cari planınız")
_p("pill.shortfall", "Shortfall risk: {v}", "Çatmazlıq riski: {v}")
_p("pill.demo_mock", "demo mock date", "demo tarixi")

# --------------------------------------------------------------------------- #
# auth
# --------------------------------------------------------------------------- #
_p("auth.customer_signin", "Customer sign in", "Müştəri girişi")
_p("auth.admin_signin", "Admin sign in", "Admin girişi")
_p("auth.customer_sub", "Tariff Advisor · demo environment",
   "Tariff Advisor · demo mühiti")
_p("auth.admin_sub", "Business dashboard · demo environment",
   "Biznes paneli · demo mühiti")
_p("auth.email", "Email", "E-poçt")
_p("auth.admin_email", "Admin email", "Admin e-poçtu")
_p("auth.password", "Password", "Şifrə")
_p("auth.signin", "Sign in", "Daxil ol")
_p("auth.demo_creds", "Demo credentials (demo mode only)",
   "Demo məlumatları (yalnız demo rejimdə)")
_p("auth.customer", "Customer", "Müştəri")
_p("auth.second_customer", "Second customer", "İkinci müştəri")
_p("auth.admin", "Admin", "Admin")
_p("auth.no_admin_here",
   "Admin sign-in is a separate page — it is not offered here.",
   "Admin girişi ayrı səhifədədir — burada təqdim olunmur.")
_p("auth.customer_link", "Customer sign-in lives at", "Müştəri girişi:")
_p("auth.invalid", "Invalid credentials for this sign-in.",
   "Bu giriş üçün etibarlı məlumat yoxdur.")

# --------------------------------------------------------------------------- #
# errors
# --------------------------------------------------------------------------- #
_p("error.back", "Back to start", "Başa qayıt")
_p("error.400", "Invalid request.", "Etibarsız sorğu.")
_p("error.403", "You do not have access to this area.",
   "Bu bölməyə giriş icazəniz yoxdur.")
_p("error.404", "Page not found.", "Səhifə tapılmadı.")
_p("error.500", "Something went wrong on our side.",
   "Bizim tərəfimizdə problem yarandı.")
_p("error.customer_not_found", "Customer not found.", "Müştəri tapılmadı.")
_p("error.bad_tariff", "That tariff does not exist in the catalog.",
   "Belə tarif kataloqda yoxdur.")

# --------------------------------------------------------------------------- #
# page titles / ledes
# --------------------------------------------------------------------------- #
_p("page.home", "Home", "Ana səhifə")
_p("page.suggested", "Suggested tariffs", "Təklif olunan tariflər")
_p("page.history", "Usage history", "İstifadə tarixçəsi")
_p("page.history_h1", "Usage & spend history", "İstifadə və xərc tarixçəsi")
_p("page.reminders", "Reminders", "Xəbərdarlıqlar")
_p("page.business", "Business dashboard", "Biznes paneli")
_p("page.customers", "Customers", "Müştərilər")

# --------------------------------------------------------------------------- #
# customer dashboard
# --------------------------------------------------------------------------- #
_p("dash.reminder_title", "Tariff end reminder", "Tarifin bitmə xəbərdarlığı")
_p("dash.open_reminders", "Open reminders", "Xəbərdarlıqları aç")
_p("dash.current_tariff", "Current tariff", "Cari tarif")
_p("dash.months_with_plan", "{n} months with this plan",
   "{n} aydır bu planda")
_p("dash.switched_recently", "switched recently · plan tenure resets on change",
   "yaxınlarda dəyişdirildi · dəyişim zamanı sıfırlanır")
_p("dash.avg_spend", "Avg. monthly spend", "Orta aylıq xərc")
_p("dash.renewal", "Renewal / end date", "Yeniləmə / bitmə tarixi")
_p("dash.mock_1", "Renewal date is a", "Yeniləmə tarixi")
_p("dash.mock_word", "demo mock", "demo təxmini")
_p("dash.mock_2", "(the workbook has no end-date field).",
   "(iş faylında bitmə tarixi sütunu yoxdur).")
_p("dash.quick_aria", "Quick links", "Sürətli keçidlər")
_p("dash.my_tariff", "My tariff", "Mənim tarifim")
_p("dash.usage", "Usage", "İstifadə")
_p("dash.reminders", "Reminders", "Xəbərdarlıqlar")
_p("dash.compare", "Compare", "Müqayisə")
_p("dash.usage_aria", "Usage summary", "İstifadə xülasəsi")
_p("dash.of_allowance", "of {v} {unit} included", "{v} {unit} daxildir")
_p("dash.allowance_unknown", "allowance unknown", "kvota məlum deyil")
_p("dash.extra_aria", "Additional internet purchases",
   "Əlavə internet alışları")
_p("dash.extra_label", "Extra internet, {n} months",
   "Əlavə internet, {n} ay")
_p("dash.extra_pack_note",
   "Extra packs cost {p} ₼ per 1 GB (catalog price). Estimate, not a bill.",
   "Əlavə paketlər 1 GB üçün {p} ₼ dir (kataloq qiyməti). Təxmin, faktura deyil.")
_p("dash.suggested_title", "Suggested tariffs", "Təklif olunan tariflər")
_p("dash.compare_all", "Compare all", "Hamısını müqayisə et")
_p("dash.unlimited", "Unlimited:", "Limitsiz:")
_p("dash.gb_internet", "internet", "internet")
_p("dash.ranked_fallback", "ranked by the rule-based model",
   "qaydalara əsaslanan model üzrə sıralanıb")
_p("dash.details", "Details", "Ətraflı")
_p("dash.no_sugg_title", "No suggestions yet.", "Hələ təkliflər yoxdur.")
_p("dash.no_sugg_1",
   "Recommendations are generated from the imported workbook. Run",
   "Təkliflər idxal olunmuş iş faylından yaradılır. Yaratmaq üçün")
_p("dash.no_sugg_2", "to build them.", "əməliyyatını işə salın.")
_p("dash.current_aria", "Current tariff summary", "Cari tarif xülasəsi")

# --------------------------------------------------------------------------- #
# recommendations page
# --------------------------------------------------------------------------- #
_p("recs.lede",
   "Rule-based ranking from your last {window} months of usage. "
   "Estimates only — no saving is guaranteed.",
   "Son {window} aylıq istifadəyə əsaslanan qaydalı sıralama. "
   "Yalnız təxminlər — heç bir qənaət zəmanətli deyil.")
_p("recs.empty_title", "No recommendation snapshot yet.",
   "Hələ təklif anlık görüntüsü yoxdur.")
_p("recs.empty_1", "Run", "İşə salın")
_p("recs.empty_2", "after importing the workbook.", "əməliyyatını idxaldan sonra.")
_p("recs.score_components", "Score components (transparent, tunable weights)",
   "Bal komponentləri (şəffaf, dəyişdirilə bilən çəkilər)")
_p("recs.component", "Component", "Komponent")
_p("recs.value", "Value", "Dəyər")
_p("recs.unknown_excluded", "unknown (excluded)", "məlum deyil (xaric edilib)")
_p("recs.weights_label", "Weights:", "Çəkilər:")
_p("recs.vs_current", "vs current, est.", "cariyə qarşı, təxmin")
_p("recs.compare_title", "Compare with your current plan",
   "Cari planınızla müqayisə")
_p("recs.your_usage", "Your est. usage", "Təxmini istifadəniz")
_p("recs.allowance", "Allowance", "Kvota")
_p("recs.extra_cost", "Extra-data cost (est.)", "Əlavə data xərci (təxmin)")
_p("recs.price_vs_current", "Price vs current", "Cariyə görə qiymət")
_p("recs.tradeoff", "Material trade-off", "Əhəmiyyətli fərq")
_p("recs.assume_1", "Assumptions: window =", "Şərtlər: dövr =")
_p("recs.assume_2",
   "; demand = mean + 0.5 × std; extra data modelled as 1 GB packs at the "
   "catalog price; roaming excluded from plan comparison (plan-independent). "
   "Unlimited-app matching is",
   "; tələb = orta + 0.5 × std; əlavə data kataloq qiyməti ilə 1 GB paketlər "
   "kimi modelləşdirilib; rouminq müqayisədən xaricdir (plandan asılı deyil). "
   "Limitsiz tətbiq uyğunluğu")
_p("recs.assume_3", "— the workbook has no app-usage field.",
   "— iş faylında tətbiq istifadəsi sütunu yoxdur.")
_p("recs.assume_strong", "not scored", "ballanmır")
_p("recs.change_title", "Change your tariff", "Tarifinizi dəyişin")
_p("recs.change_lede",
   "Pick any plan from the catalog. Your dashboard, utilization and "
   "suggestion are refreshed immediately; the new plan's renewal date is "
   "unknown (not present in the source data).",
   "Kataloqdan istənilən planı seçin. Paneliniz, istifadə faizi və təklif "
   "dərhal yenilənir; yeni planın yeniləmə tarixi məlum deyil (mənbə "
   "məlumatlarında yoxdur).")
_p("recs.change_foot_1", "Demo user action — recorded in the",
   "Demo istifadəçi əməliyyatı —")
_p("recs.change_foot_2",
   "audit log. Changing your tariff does not alter the imported workbook data.",
   "audit jurnalına yazılır. Tarifinizi dəyişmək idxal olunmuş iş faylını "
   "dəyişdirmir.")
_p("recs.aria_ranked", "Ranked plans", "Sıralanmış planlar")

# --------------------------------------------------------------------------- #
# spec grid / table headers
# --------------------------------------------------------------------------- #
_p("spec.internet", "Internet", "İnternet")
_p("spec.calls", "Calls", "Danışıqlar")
_p("spec.sms", "SMS", "SMS")
_p("spec.est_cost", "Est. total cost", "Təxmini cəmi xərc")
_p("spec.unlimited", "Unlimited apps", "Limitsiz tətbiqlər")
_p("spec.score", "Score", "Bal")
_p("spec.any_net", "(any network)", "(bütün şəbəkələr)")
_p("spec.onoff_net", "(on+off net)", "(şəbəkədaxili+xarici)")
_p("spec.none_listed", "none listed", "göstərilməyib")

_p("th.plan", "Plan", "Plan")
_p("th.price", "Price", "Qiymət")
_p("th.minutes", "Minutes", "Dəqiqələr")
_p("th.action", "Action", "Əməliyyat")
_p("th.month", "Month", "Ay")
_p("th.tariff", "Tariff", "Tarif")
_p("th.data", "Data (GB)", "Data (GB)")
_p("th.sms", "SMS", "SMS")
_p("th.extra_internet", "Extra internet (GB)", "Əlavə internet (GB)")
_p("th.extra_gb", "Extra GB", "Əlavə GB")
_p("th.oob", "Out-of-pkg min", "Paketdən kənar dəq")
_p("th.topups", "Top-ups", "Balans artımları")
_p("th.roaming", "Roaming days", "Rouminq günləri")
_p("th.spend", "Spend (AZN)", "Xərc (AZN)")
_p("th.total", "Total", "Cəmi")
_p("th.customer_id", "Customer ID", "Müştəri ID")
_p("th.current_tariff", "Current tariff", "Cari tarif")
_p("th.current_price", "Current price", "Cari qiymət")
_p("th.rec_tariff", "Recommended tariff", "Təklif olunan tarif")
_p("th.rec_price", "Recommended price", "Təklif olunan qiymət")
_p("th.reason", "Reason", "Səbəb")
_p("th.reasons", "Reasons", "Səbəblər")
_p("th.generated", "Generated", "Yaradılma")
_p("th.metric", "Metric", "Metrik")
_p("th.status", "Status", "Status")
_p("th.family", "Family", "Ailə")
_p("th.price_azn", "Price (AZN)", "Qiymət (AZN)")
_p("th.internet_gb", "Internet (GB)", "İnternet (GB)")
_p("th.allnet", "All-net min", "Bütün şəbəkə dəq")
_p("th.onnet", "On-net", "Şəbəkədaxili")
_p("th.offnet", "Off-net", "Şəbəkəxarici")
_p("th.unlimited_apps", "Unlimited apps", "Limitsiz tətbiqlər")
_p("th.provenance", "Provenance", "Mənbə")
_p("th.data_cover", "Data cover", "Data əhatəsi")
_p("th.calls_cover", "Calls cover", "Danışıq əhatəsi")
_p("th.rank", "#", "#")

# --------------------------------------------------------------------------- #
# usage history page
# --------------------------------------------------------------------------- #
_p("hist.lede", "Monthly records exactly as imported from the workbook ({n} months).",
   "Aylıq qeydlər iş faylına idxal olunduğu kimi ({n} ay).")
_p("hist.empty_title", "No usage records.", "İstifadə qeydləri yoxdur.")
_p("hist.empty_1", "Import the workbook first:", "Əvvəlcə iş faylını idxal edin:")
_p("hist.internet", "Internet (GB)", "İnternet (GB)")
_p("hist.call_minutes", "Call minutes", "Danışıq dəqiqələri")
_p("hist.spend", "Spend (AZN)", "Xərc (AZN)")
_p("hist.details", "Details", "Ətraflı")
_p("hist.renewal", "Tariff renewal", "Tarif yeniləməsi")
_p("hist.aria_internet", "Monthly internet usage", "Aylıq internet istifadəsi")
_p("hist.aria_calls", "Monthly call usage", "Aylıq danışıq istifadəsi")
_p("hist.aria_spend", "Monthly spend", "Aylıq xərc")
_p("hist.aria_details", "Detailed monthly records", "Ətraflı aylıq qeydlər")
_p("hist.aria_renewal", "Upcoming tariff renewal", "Yaxınlaşan tarif yeniləməsi")
_p("hist.allow_gb", "Plan allowance: {v} GB / month",
   "Plan kvotası: {v} GB / ay")
_p("hist.allow_min", "Plan allowance: {v} min / month",
   "Plan kvotası: {v} dəq / ay")
_p("hist.footnote",
   "Additional internet purchases are billed as 1 GB packs; totals above are "
   "observed values from the source data.",
   "Əlavə internet alışları 1 GB paketlər kimi hesablanır; yuxarıdakı cəmlər "
   "mənbə məlumatlarından alınmış göstəricilərdir.")
_p("hist.renewal_1", "Current tariff", "Cari tarif")
_p("hist.renewal_2", "period ends on", "dövrü tarixində bitir")
_p("hist.no_end_1", "Upcoming tariff end date is not available",
   "Yaxınlaşan tarifin bitmə tarixi mövcud deyil")
_p("hist.no_end_2",
   "— the source workbook has no end-date field, so nothing can be shown "
   "here without inventing data.",
   "— iş faylında bitmə tarixi sütunu yoxdur, buna görə də uydurmadan burada "
   "heç nə göstərmək mümkün deyil.")
_p("hist.reminder_settings", "Reminder settings", "Xəbərdarlıq parametrləri")

# --------------------------------------------------------------------------- #
# notifications page
# --------------------------------------------------------------------------- #
_p("notif.lede",
   "In-app demo notifications. Five days before a tariff period ends you get "
   "one reminder per period — repeated runs never duplicate it.",
   "Tətbiqdaxili demo bildirişləri. Tarif dövrü bitməzdən beş gün əvvəl dövr "
   "başına bir xəbərdarlıq alırsınız — təkrar işə salmalar onu kopyalamır.")
_p("notif.prefs_title", "Notification preferences", "Bildiriş üstünlükləri")
_p("notif.in_app_label", "In-app tariff-end reminders",
   "Tətbiqdaxili tarif bitmə xəbərdarlıqları")
_p("notif.prefs_foot",
   "Turning this off makes future reminder runs skip your account "
   "(the skip is recorded). Push/SMS delivery is not available in this demo "
   "— no provider is configured, so nothing leaves this app.",
   "Bu söndürülsə, gələcək xəbərdarlıq yoxlamaları hesabınızı atlayır "
   "(atlanma qeyd olunur). Bu demo-də push/SMS çatdırılma mövcud deyil — "
   "heç bir təchizatçı konfiqurasiya olunmayıb, heç nə tətbiqdən kənar çıxmır.")
_p("notif.your", "Your notifications", "Sizin bildirişləriniz")
_p("notif.type_reminder", "Tariff-end reminder", "Tarif bitmə xəbərdarlığı")
_p("notif.meta", "Period key: {key} · status: {status}",
   "Dövr açarı: {key} · status: {status}")
_p("notif.due", "due {at}", "bitmə: {at}")
_p("notif.status_pending", "pending", "gözləyir")
_p("notif.status_read", "read", "oxunub")
_p("notif.empty_title", "No reminders yet.", "Hələ xəbərdarlıq yoxdur.")
_p("notif.empty_body",
   "A reminder appears {w} days before a tariff period ends. The source "
   "workbook contains no end dates, so demo-mock dates are used for seeded "
   "demo customers only — see README.",
   "Xəbərdarlıq tarif dövrü bitməzdən {w} gün əvvəl görünür. Mənbə iş faylında "
   "bitmə tarixləri yoxdur, buna görə demo tarixləri yalnız əkilmiş demo "
   "müştərilər üçün istifadə olunur — README-yə baxın.")
_p("notif.trigger", "Trigger manually:", "Əl ilə işə salın:")
_p("notif.skips_title", "Skipped reminder checks", "Atlanmış yoxlama qeydləri")
_p("notif.no_period", "no period", "dövr yoxdur")
_p("notif.no_skips", "No skips recorded for your account.",
   "Hesabınız üçün atlanma qeydi yoxdur.")
_p("notif.tz_foot",
   "Timezone for reminder scheduling: Asia/Baku (demo default). "
   "Delivery claim: in-app only.",
   "Xəbərdarlıq cədvəli zaman qurşağı: Asia/Baku (demo susayarı). "
   "Çatdırılma: yalnız tətbiqdaxili.")
_p("notif.aria_prefs", "Notification preferences", "Bildiriş üstünlükləri")
_p("notif.aria_list", "Notification list", "Bildiriş siyahısı")
_p("notif.aria_skips", "Skipped reminder checks", "Atlanmış yoxlama qeydləri")

_p("skip.missing_end_date", "missing tariff end date",
   "tarifin bitmə tarixi yoxdur")
_p("skip.invalid_end_date", "invalid tariff end date",
   "tarifin bitmə tarixi etibarsızdır")
_p("skip.opted_out", "customer opted out of reminders",
   "müştəri xəbərdarlıqlardan imtina edib")
_p("skip.period_already_ended", "tariff period already ended",
   "tarif dövrü artıq bitib")

# --------------------------------------------------------------------------- #
# notification bodies (rendered from stored params at display time)
# --------------------------------------------------------------------------- #
_p("notif.reminder_body",
   "Demo reminder: your tariff {tariff} period ends on {end} (in {days} {day}). "
   "This is an in-app demo notification — push/SMS delivery is not configured.",
   "Demo xəbərdarlıq: {tariff} tarifinizin dövrü {end} tarixində bitir "
   "({days} {day}). Bu tətbiqdaxili demo bildirişidir — push/SMS çatdırılma "
   "konfiqurasiya olunmayıb.")
_p("notif.day_one", "day", "günd")
_p("notif.day_many", "days", "günd")

# --------------------------------------------------------------------------- #
# admin dashboard
# --------------------------------------------------------------------------- #
_p("admin.signout", "Sign out", "Çıxış")
_p("admin.nav_dashboard", "Dashboard", "Panel")
_p("admin.nav_customers", "Customers", "Müştərilər")
_p("admin.dash_lede_1",
   "All figures are computed from the imported synthetic workbook and "
   "reconcile with",
   "Bütün rəqəmlər idxal olunmuş süni iş faylından hesablanır və")
_p("admin.dash_lede_2",
   ". Unsupported metrics are marked unavailable — never shown as zero.",
   " nəticələri ilə uyğundur. Dəstəklənməyən metriklər əlçatmaz kimi "
   "göstərilir — heç vaxt sıfır kimi deyil.")
_p("admin.filters_aria", "Dashboard filters", "Panel filtrləri")
_p("admin.cust_filters_aria", "Customer filters", "Müştəri filtrləri")
_p("admin.summary_aria", "Summary", "Xülasə")
_p("stat.total_customers", "Total customers", "Ümumi müştərilər")
_p("stat.over_allowance", "Customers over data allowance",
   "Kvotadan artıq müştərilər")
_p("stat.avg_spend", "Avg. monthly spend", "Orta aylıq xərc")
_p("stat.extra_bought", "Additional internet bought", "Alınan əlavə internet")
_p("stat.utilization_avg", "Utilization (avg)", "İstifadə faizi (orta)")
_p("stat.addon", "Add-on spend (est.)", "Əlavə xərc (təxmin)")
_p("admin.all_tariffs", "all tariffs", "bütün tariflər")
_p("admin.tariff_eq", "tariff={t}", "tarif={t}")
_p("admin.foot_over",
   "6-month average vs plan GB · {a} of {b} month-records exceeded",
   "6 ay orta vs plan GB · {b} aylıq qeyddən {a} si aşılıb")
_p("admin.foot_unknown_util",
   "+ {n} unknown (0 GB plan → utilization undefined)",
   "+ {n} məlum deyil (0 GB plan → istifadə faizi qeyri-müəyyən)")
_p("admin.foot_records", "{n} month-records · observed, not forecast",
   "{n} aylıq qeyd · müşahidə olunmuş, proqnoz deyil")
_p("admin.unavail_no_rows", "Unavailable — no usage rows for this filter",
   "Əlçatmaz — bu filtr üçün istifadə sətiri yoxdur")
_p("admin.foot_unit_unknown", "Unit price unknown → cost not computed",
   "Vahid qiymət məlum deyil → xərc hesablanmayıb")
_p("admin.unavail_filter", "Unavailable for this filter",
   "Bu filtr üçün əlçatmaz")
_p("admin.foot_min_util", "{n}% of minutes allowance",
   "dəqiqə kvotasının {n}%-i")
_p("admin.foot_unknown_customers", "{n} customer(s) unknown (0 GB plan)",
   "{n} müştəri məlum deyil (0 GB plan)")
_p("admin.addon_split",
   "extra data {extra} + out-of-bundle {oob} + roaming {roam}",
   "əlavə data {extra} + paketdən kənar {oob} + rouminq {roam}")
_p("admin.stat_prices_missing", "Unit prices missing in catalog",
   "Kataloqda vahid qiymətlər yoxdur")
_p("admin.unavail_no_rows_short", "Unavailable — no usage rows",
   "Əlçatmaz — istifadə sətirləri yoxdur")
_p("chart.tariff_dist", "Tariff distribution", "Tarif paylanması")
_p("chart.usage_vs", "Usage vs allowance (month-records)",
   "İstifadə vs kvota (aylıq qeydlər)")
_p("chart.rec_dist", "Recommendation distribution (top pick)",
   "Təklif paylanması (ilk seçim)")
_p("admin.no_customers", "No customers imported.", "Müştəri idxal olunmayıb.")
_p("bar.within_data", "Within data allowance", "Kvota daxilində (data)")
_p("bar.over_data", "Over data allowance", "Kvotadan artıq (data)")
_p("bar.over_min", "Over minute allowance", "Kvotadan artıq (dəqiqə)")
_p("bar.bought_extra", "Bought extra internet", "Əlavə internet alınıb")
_p("admin.see_table", "See per-customer table →",
   "Müştəri-başına cədvələ bax →")
_p("admin.no_snap_1", "No recommendation snapshots yet — run",
   "Hələ təklif anlıq görüntüsü yoxdur — işə salın:")
_p("admin.no_snap_2", ".", ".")
_p("admin.unsup_title", "Metrics not supported by the dataset",
   "Dataset tərəfindən dəstəklənməyən metriklər")
_p("admin.catalog_title", "Package catalog (source-supported only)",
   "Paket kataloqu (yalnız mənbə dəstəklidir)")
_p("admin.cat_foot_1", "Catalog rows come only from the workbook's",
   "Kataloq sətirləri yalnız iş faylının")
_p("admin.cat_foot_2",
   "sheet; missing cells stay “unknown” and are excluded from scoring.",
   " səhifəsindən götürülür; boş xanalar “məlum deyil” qalır və ballanmadan "
   "xaric edilir.")
_p("admin.aria_filters", "Dashboard filters", "Panel filtrləri")

# --------------------------------------------------------------------------- #
# admin customers table + detail
# --------------------------------------------------------------------------- #
_p("admin.customers_h1", "Customers & recommendations",
   "Müştərilər və təkliflər")
_p("admin.customers_lede",
   "Customer IDs only — phone numbers are not stored, logged or displayed "
   "anywhere in this app.",
   "Yalnız müştəri ID-ləri — nömrələr bu tətbiqdə heç yerdə saxlanılmır, "
   "jurnal yazılmır və göstərilmir.")
_p("admin.table_counts", "{n} customer(s) · page {p} of {P}",
   "{n} müştəri · səhifə {p} / {P}")
_p("admin.no_match", "No customers match this filter.",
   "Bu filtrə uyğun müştəri yoxdur.")
_p("admin.detail_lede",
   "{tariff} · {region} · {type} · {tenure} months on network · phone number:",
   "{tariff} · {region} · {type} · {tenure} ay şəbəkədə · telefon nömrəsi:")
_p("admin.not_stored", "not stored", "saxlanılmayıb")
_p("stat.current_plan", "Current plan", "Cari plan")
_p("stat.averages_6m", "6-month averages", "6 ay orta göstəricilər")
_p("stat.utilization", "Utilization", "İstifadə faizi")
_p("stat.extra_6m", "Extra internet (6 mo)", "Əlavə internet (6 ay)")
_p("admin.renewal_label", "Renewal date:", "Yeniləmə tarixi:")
_p("admin.latest_rec", "Latest recommendation", "Son təklif")
_p("admin.window_foot", "Window {a} → {b} · weights {w}",
   "Dövr {a} → {b} · çəkilər {w}")
_p("admin.window_label", "Window: {a} → {b}", "Dövr: {a} → {b}")
_p("admin.at_catalog", "at catalog price (estimate)",
   "kataloq qiyməti ilə (təxmin)")
_p("admin.no_snap_customer",
   "No recommendation snapshot for this customer yet.",
   "Bu müştəri üçün hələ təklif anlıq görüntüsü yoxdur.")
_p("admin.monthly_usage", "Monthly usage", "Aylıq istifadə")
_p("admin.aria_crumbs", "Breadcrumb", "Yol göstəricisi")

# --------------------------------------------------------------------------- #
# unsupported-metric texts (admin dashboard)
# --------------------------------------------------------------------------- #
_p("unsup.push_name", "Push / SMS delivery", "Push / SMS çatdırılma")
_p("unsup.push_reason",
   "No push or SMS provider credentials are configured; reminders are "
   "in-app demo notifications only.",
   "Push və ya SMS təchizatçı məlumatları konfiqurasiya olunmayıb; "
   "xəbərdarlıqlar yalnız tətbiqdaxili demo bildirişləridir.")
_p("unsup.apps_name", "Unlimited-app fit per customer",
   "Müştəriyə görə limitsiz tətbiq uyğunluğu")
_p("unsup.apps_reason",
   "The workbook has no app-usage field, so the app-usage side of the match "
   "is unknown.",
   "İş faylında tətbiq istifadəsi sütunu yoxdur, buna görə uyğunluğun tətbiq "
   "tərəfi məlum deyil.")
_p("unsup.end_name", "Tariff end dates (source)", "Tarif bitmə tarixləri (mənbə)")
_p("unsup.end_reason",
   "No end-date column exists in the workbook; {n} customer(s) still have no "
   "date (demo mocks only for seeded demo customers).",
   "İş faylında bitmə tarixi sütunu yoxdur; {n} müştərinin hələ də tarixi yoxdur "
   "(demo tarixləri yalnız əkilmiş demo müştərilər üçün).")
_p("unsup.churn_name", "Churn / revenue / ARPU",
   "Churn / gəlir / ARPU")
_p("unsup.churn_reason", "No contract, revenue or churn fields in the source data.",
   "Mənbə məlumatlarında müqavilə, gəlir və ya churn sahələri yoxdur.")
_p("analytics.no_rows_reason", "no usage rows for this filter",
   "bu filtr üçün istifadə sətiri yoxdur")

# --------------------------------------------------------------------------- #
# admin reason sentences (plain language, never keywords)
# --------------------------------------------------------------------------- #
_p("reason.fallback", "scored by the rule-based model",
   "qaydalara əsaslanan model balı ilə sıralanıb")
_p("reason.other", "an additional model factor", "əlavə model amili")
_p("reason.keeps_current", "the customer's current plan already ranks best",
   "müştərinin cari tarifi artıq ən yaxşı sıralanır")
_p("reason.covers_data", "covers the estimated internet demand",
   "təxmini internet tələbini ödəyir")
_p("reason.covers_calls", "covers the estimated call demand",
   "təxmini danışıq tələbini ödəyir")
_p("reason.shortfall_data",
   "does not fully cover the estimated internet demand (shortfall risk)",
   "təxmini internet tələbini tam ödəmir (çatmazlıq riski)")
_p("reason.shortfall_calls",
   "does not fully cover the estimated call demand (shortfall risk)",
   "təxmini danışıq tələbini tam ödəmir (çatmazlıq riski)")
_p("reason.cheaper_than_current",
   "estimated monthly cost is lower than the current plan",
   "təxmini aylıq xərc cari plandan aşağıdır")
_p("reason.dearer_than_current",
   "estimated monthly cost is higher than the current plan",
   "təxmini aylıq xərc cari plandan yuxarıdır")
_p("reason.same_cost_as_current",
   "estimated monthly cost is about the same as the current plan",
   "təxmini aylıq xərc cari planla təxminən eynidir")
_p("reason.unknown_data_allowance",
   "the catalog does not list this plan's internet allowance",
   "kataloqda bu planın internet kvotası göstərilməyib")
_p("reason.no_unlimited_apps_listed",
   "no unlimited apps are listed for this plan",
   "bu plan üçün limitsiz tətbiqlər göstərilməyib")
_p("reason.estimated_cost_known",
   "an estimated monthly cost was computed from catalog prices",
   "kataloq qiymətlərindən təxmini aylıq xərc hesablandı")

# --------------------------------------------------------------------------- #
# recommendation explanations (generated at display time from stored facts)
# --------------------------------------------------------------------------- #
_p("expl.unknown_amount", "an unknown amount", "məlum olmayan məbləğ")
_p("expl.disclaimer",
   "Estimates are computed from your observed usage in the selected window "
   "and the catalog's published allowances. Actual bills can differ — "
   "no saving is guaranteed.",
   "Təxminlər seçilmiş dövrdə müşahidə olunan istifadəniz və kataloqun "
   "açıqlanmış kvotaları əsasında hesablanır. Faktura fərqlənə bilər — "
   "heç bir qənaət zəmanətli deyil.")
_p("expl.allow_no_data",
   "its internet allowance is not in the catalog, so the data fit is unknown",
   "internet kvotası kataloqda yoxdur, buna görə data uyğunluğu məlum deyil")
_p("expl.min_any_net", "{m} minutes on any network",
   "{m} dəqiqə bütün şəbəkələr üzrə")
_p("expl.min_onnet", "{m} on-net minutes", "{m} şəbəkədaxili dəqiqə")
_p("expl.min_offnet", "{m} off-net minutes", "{m} şəbəkəxarici dəqiqə")
_p("expl.min_unknown", "an unknown number of minutes",
   "məlum olmayan dəqiqə sayı")
_p("expl.allowance_includes", "it includes {gb} of internet and {minpart}",
   "bura {gb} internet və {minpart} daxildir")
_p("expl.no_reco", "No recommendation could be produced for this account.",
   "Bu hesab üçün təklif hazırlamaq mümkün olmadı.")
_p("expl.summary_usage",
   "Over {n} month(s) ({months}) you used about {gb} GB and {min} minutes "
   "per month on average, and bought {extra} GB of extra internet per month.",
   "{n} ay ərzində ({months}) orta hesabla ayda təxminən {gb} GB və {min} "
   "dəqiqə istifadə etdiniz və ayda {extra} GB əlavə internet aldınız.")
_p("expl.summary_current_best",
   "Your current plan {name} scores highest — keeping it is the "
   "best-supported option right now.",
   "Cari planınız {name} ən yüksək balı toplayır — onu saxlamaq hazırda "
   "ən yaxşı dəstəklənən variantdır.")
_p("expl.summary_rank_first",
   "{name} ranks first: {allowance}, at an estimated {cost} per month "
   "including likely extra-data costs.",
   "{name} birinci sıradadır: {allowance}, ehtimal olunan əlavə data "
   "xərcləri ilə birlikdə ayda təxminən {cost}.")
_p("expl.summary_shortfall_warn",
   "Warning: no candidate fully covers your estimated demand, so at least one "
   "of these options may still leave a shortfall.",
   "Xəbərdarlıq: heç bir variant təxmini tələbinizi tam ödəmir, buna görə bu "
   "variantlardan ən azı biri çatmazlıq yarada bilər.")
_p("expl.summary_current_included",
   "Your current plan {name} is included in the comparison (ranked #{n}).",
   "Cari planınız {name} müqayisəyə daxildir (№{n} sıralanıb).")
_p("expl.plan_head", "{name}: {allowance}", "{name}: {allowance}")
_p("expl.cost_current",
   "It is estimated to cost {est} per month (plan price {price} plus likely "
   "extras).",
   "Aylıq təxmini xərci {est} təşkil edir (plan qiyməti {price} plus ehtimal "
   "olunan əlavələr).")
_p("expl.less", "less", "az")
_p("expl.more", "more", "çox")
_p("expl.cost_same",
   "Its estimated monthly cost ({est}) is about the same as your current "
   "plan ({cur}).",
   "Təxmini aylıq xərci ({est}) cari planınızla ({cur}) təxminən eynidir.")
_p("expl.cost_diff",
   "It is estimated to cost {est} per month, about {diff} {dir} than your "
   "current plan ({cur}).",
   "Aylıq təxmini xərci {est} təşkil edir — bu, cari planınızdan ({cur}) "
   "təxminən {diff} {dir}.")
_p("expl.cost_est_only", "Estimated monthly cost: {est}.",
   "Təxmini aylıq xərc: {est}.")
_p("expl.data_fits",
   "Your estimated {used} GB monthly demand fits inside the {allow} GB "
   "allowance.",
   "Təxmini {used} GB aylıq tələbiniz {allow} GB kvota daxilindədir.")
_p("expl.data_exceeds",
   "Your estimated {used} GB monthly demand exceeds the {allow} GB allowance "
   "by {over} GB — you would likely still buy extra internet.",
   "Təxmini {used} GB aylıq tələbiniz {allow} GB kvotanı {over} GB aşıb — "
   "ehtimal olaraq yenə də əlavə internet alacaqsınız.")
_p("expl.calls_unknown",
   "Your call usage fit is unknown (missing allowance data).",
   "Danışıq istifadənizin uyğunluğu məlum deyil (kvota məlumatları yoxdur).")
_p("expl.calls_fit",
   "Your estimated {n} minutes of monthly calls fit within the plan's minute "
   "allowance.",
   "Təxmini {n} dəqiqəlik aylıq danışıqlarınız planın dəqiqə kvotası "
   "daxilindədir.")
_p("expl.calls_partial",
   "Your estimated call demand may not fit: the plan's known minute "
   "allowance covers about {pct}% of your typical monthly minutes.",
   "Təxmini danışıq tələbiniz uyğun gəlməyə bilər: planın məlum dəqiqə "
   "kvotası adi aylıq dəqiqələrinizin təxminən {pct}%-ini əhatə edir.")
_p("expl.shortfall_warn",
   "Shortfall warning ({s}): this plan does not fully cover estimated demand.",
   "Çatmazlıq xəbərdarlığı ({s}): bu plan təxmini tələbi tam örtmür.")
_p("expl.is_current_note",
   "This is your current plan — if it stays the top-ranked option, keeping "
   "it is the recommendation.",
   "Bu sizin cari planınızdır — ən yaxşı sıralanıb qalsa, onu saxlamaq "
   "tövsiyə olunur.")
_p("expl.bul_extra_bought",
   "You bought {x} GB extra per month on average (about {c}/month).",
   "Orta hesabla ayda {x} GB əlavə aldınız (ayda təxminən {c}).")
_p("expl.bul_extras_1",
   "Estimated extras on this plan: {packs} extra-data pack(s) ≈ {cost}",
   "Bu planda təxmini əlavələr: {packs} əlavə-data paketi ≈ {cost}")
_p("expl.bul_extras_2", " + {m} out-of-package minutes ≈ {c}",
   " + {m} paketdən kənar dəqiqə ≈ {c}")
_p("expl.bul_excess",
   "About {x} GB of the allowance would likely be unused (oversupply).",
   "Kvotanın təxminən {x} GB-ı istifadə olunmaya bilər (artıq təminat).")
_p("expl.bul_apps",
   "Listed unlimited apps: {apps} (catalog fact; your app usage is not in "
   "the data).",
   "Göstərilən limitsiz tətbiqlər: {apps} (kataloq faktı; tətbiq istifadəniz "
   "məlumatlarda yoxdur).")
_p("expl.bul_spend", "Observed average monthly spend: {s}.",
   "Müşahidə olunan orta aylıq xərc: {s}.")
_p("expl.sr_covers", "covers your ~{g} GB need",
   "~{g} GB tələbinizi ödəyir")
_p("expl.sr_less_data", "less data than your estimated need",
   "təxmini tələbinizdən az data")
_p("expl.sr_calls_fit", "calls fit", "danışıqlar uyğundur")
_p("expl.sr_calls_maybe", "calls may not fit", "danışıqlar uyğun gəlməyə bilər")
_p("expl.sr_cheaper", "≈{d} AZN cheaper (est.)", "≈{d} AZN daha ucuz (təxmin)")
_p("expl.sr_dearer", "≈{d} AZN dearer (est.)", "≈{d} AZN daha bahalı (təxmin)")
_p("expl.sr_same_cost", "same est. cost as current",
   "cari ilə eyni təxmini xərc")
_p("expl.sr_current", "your current plan", "sizin cari planınız")
_p("expl.sr_excess", "{x} GB likely unused", "{x} GB istifadə olunmaya bilər")
_p("expl.sr_fallback", "ranked by rule-based score",
   "qaydalara əsaslanan bal ilə sıralanıb")
_p("expl.weights_note",
   "Scoring weights — adequacy {a}, cost {c}, oversupply {o}, "
   "affordability {f} (unknown components are excluded and remaining weights "
   "renormalised).",
   "Bal çəkiləri — uyğunluq {a}, xərc {c}, artıq təminat {o}, əlçatanlıq {f} "
   "(məlum olmayan komponentlər xaric edilir və qalan çəkilər yenidən "
   "normallaşdırılır).")

# --------------------------------------------------------------------------- #
# flash messages
# --------------------------------------------------------------------------- #
_p("flash.changed",
   "Tariff changed: {old} → {new} ({price} AZN/month). Recommendations "
   "refreshed; the renewal date for the new plan is unknown (not in source "
   "data).",
   "Tarif dəyişdi: {old} → {new} ({price} AZN/ay). Təkliflər yeniləndi; "
   "yeni planın yeniləmə tarixi məlum deyil (mənbə məlumatlarında yoxdur).")
_p("flash.already", "You are already on {tariff}.",
   "Siz artıq {tariff} planındasınız.")
_p("trade.shortfall",
   "Does not fully cover estimated demand ({v}).",
   "Təxmini tələbi tam ödəmir ({v}).")
_p("trade.excess", "~{x} GB allowance may go unused.",
   "~{x} GB kvota istifadə olunmaya bilər.")
_p("trade.calls", "Estimated call minutes may exceed the allowance.",
   "Təxmini danışıq dəqiqələri kvotadan artıq ola bilər.")
_p("trade.none", "No material trade-off detected within the known catalog data.",
   "Məlum kataloq məlumatlarında əhəmiyyətli fərq aşkarlanmadı.")

STRINGS: dict[str, dict[str, str]] = {"en": _EN, "az": _AZ}


def translate(locale: str | None, key: str, /, **params) -> str:
    """Translate ``key`` into ``locale`` (falls back to EN, then to the key).

    ``locale`` and ``key`` are positional-only so format params may freely use
    names like ``key`` or ``locale`` (e.g. ``notif.meta``).
    """
    table = STRINGS.get(locale or DEFAULT_LOCALE) or {}
    text = table.get(key)
    if text is None:
        text = _EN.get(key, key)
    try:
        return text.format(**params) if params else text
    except (KeyError, IndexError, ValueError):
        return text


def get_locale() -> str:
    """Active locale for the current request/session (Flask-aware)."""
    try:
        from flask import session

        lang = session.get("lang")
        if lang in LOCALES:
            return lang
    except RuntimeError:  # outside request context (scripts, CLI)
        pass
    return DEFAULT_LOCALE


def tx(key: str, /, **params) -> str:
    """Translate for the active session locale (controller-side helper)."""
    return translate(get_locale(), key, **params)


def describe_reasons(codes: list | None, locale: str | None = None, *, limit: int = 4) -> str:
    """Turn machine reason codes into one plain-language sentence.

    Used by the admin panel so reasons read as text, never as keywords.
    """
    lang = locale or DEFAULT_LOCALE
    clauses: list[str] = []
    for code in codes or []:
        if code == "unlimited_apps_match_unknown":
            continue  # noisy: app usage is never scored in this dataset
        text = translate(lang, f"reason.{code}")
        if text == f"reason.{code}":
            text = translate(lang, "reason.other")
        clauses.append(text)
        if len(clauses) >= limit:
            break
    if not clauses:
        return translate(lang, "reason.fallback")
    sentence = "; ".join(clauses)
    return sentence[0].upper() + sentence[1:] + "."
