package sk.zevsflow.officeflow.ui

const val HOME_ROUTE = "home"
const val INVOICE_LIST_ROUTE = "invoices"
const val CONTACT_LIST_ROUTE = "contacts"
const val VOICE_CHAT_LABEL = "Hlas / Chat"

enum class C1Availability {
    EXISTING_INVOICES,
    EXISTING_CONTACTS,
    UNAVAILABLE,
}

data class BusinessSublevel(
    val id: String,
    val label: String,
    val canonicalOwner: String? = null,
    val availability: C1Availability = C1Availability.UNAVAILABLE,
)

data class BusinessDomain(
    val id: String,
    val label: String,
    val sublevels: List<BusinessSublevel>,
)

val C1_BUSINESS_DOMAINS: List<BusinessDomain> = listOf(
    BusinessDomain(
        id = "invoices",
        label = "Faktúry",
        sublevels = listOf(
            BusinessSublevel("create", "Vytvoriť faktúru", "create_invoice"),
            BusinessSublevel(
                "existing",
                "Existujúce faktúry",
                availability = C1Availability.EXISTING_INVOICES,
            ),
            BusinessSublevel("edit", "Upraviť faktúru", "edit_existing_invoice"),
            BusinessSublevel("paid", "Označiť ako uhradenú", "mark_existing_invoice_paid"),
            BusinessSublevel("delete", "Vymazať faktúru", "delete_existing_invoice"),
        ),
    ),
    BusinessDomain(
        id = "receipts",
        label = "Bločky",
        sublevels = listOf(
            BusinessSublevel("add", "Pridať bloček", "add_receipt"),
            BusinessSublevel("existing", "Existujúce bločky", "show_recent_accounting_documents"),
        ),
    ),
    BusinessDomain(
        id = "contacts",
        label = "Kontakty",
        sublevels = listOf(
            BusinessSublevel(
                "existing",
                "Existujúce kontakty",
                availability = C1Availability.EXISTING_CONTACTS,
            ),
            BusinessSublevel("add", "Pridať kontakt", "add_contact"),
        ),
    ),
    BusinessDomain(
        id = "work-time",
        label = "Pracovný čas",
        sublevels = listOf(
            BusinessSublevel("open", "Začať pracovný deň", "open_work_day"),
            BusinessSublevel("close", "Ukončiť pracovný deň", "close_work_day"),
            BusinessSublevel("add", "Pridať čas", "add_work_time_entry"),
            BusinessSublevel("report", "Mesačný report", "generate_work_time_report"),
            BusinessSublevel("break", "Nastavenie prestávky", "update_work_time_lunch_break"),
            BusinessSublevel("delete-month", "Vymazať mesiac", "delete_work_time_month"),
        ),
    ),
    BusinessDomain(
        id = "analytics",
        label = "Analytika",
        sublevels = listOf(
            BusinessSublevel("invoices", "Faktúry", "invoice_analytics"),
            BusinessSublevel("receipts", "Bločky", "accounting_document_analytics"),
        ),
    ),
    BusinessDomain(
        id = "infohelp",
        label = "InfoHelp",
        sublevels = emptyList(),
    ),
)

fun businessDomain(domainId: String?): BusinessDomain? =
    C1_BUSINESS_DOMAINS.singleOrNull { it.id == domainId }

fun businessSublevel(domainId: String?, sublevelId: String?): BusinessSublevel? =
    businessDomain(domainId)?.sublevels?.singleOrNull { it.id == sublevelId }

fun domainRoute(domainId: String): String = "domain/$domainId"

fun unavailableRoute(domainId: String, sublevelId: String): String =
    "domain/$domainId/unavailable/$sublevelId"
