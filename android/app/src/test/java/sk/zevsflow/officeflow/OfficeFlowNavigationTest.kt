package sk.zevsflow.officeflow

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import sk.zevsflow.officeflow.ui.C1Availability
import sk.zevsflow.officeflow.ui.C1_BUSINESS_DOMAINS
import sk.zevsflow.officeflow.ui.HOME_ROUTE
import sk.zevsflow.officeflow.ui.VOICE_CHAT_LABEL
import sk.zevsflow.officeflow.ui.businessDomain

class OfficeFlowNavigationTest {
    @Test fun homeHasExactlyTheSixFrozenBusinessDomains() {
        assertEquals(
            listOf("Faktúry", "Bločky", "Kontakty", "Pracovný čas", "Analytika", "InfoHelp"),
            C1_BUSINESS_DOMAINS.map { it.label },
        )
        assertEquals("home", HOME_ROUTE)
        assertEquals("Hlas / Chat", VOICE_CHAT_LABEL)
        assertFalse(C1_BUSINESS_DOMAINS.any { it.label == "Doklady" })
    }

    @Test fun onlyExistingInvoicesAndContactsAreNetworkCapableInC1() {
        val available = C1_BUSINESS_DOMAINS.flatMap { domain ->
            domain.sublevels.map { domain.id to it }
        }.filter { (_, sublevel) -> sublevel.availability != C1Availability.UNAVAILABLE }

        assertEquals(
            listOf("invoices" to "Existujúce faktúry", "contacts" to "Existujúce kontakty"),
            available.map { (domainId, sublevel) -> domainId to sublevel.label },
        )
        assertTrue(businessDomain("infohelp")?.sublevels?.isEmpty() == true)
        assertNull(businessDomain("unknown"))
    }

    @Test fun invoiceAndWorkTimeSublevelsMatchTheFrozenDesign() {
        assertEquals(
            listOf(
                "Vytvoriť faktúru",
                "Existujúce faktúry",
                "Upraviť faktúru",
                "Označiť ako uhradenú",
                "Vymazať faktúru",
            ),
            businessDomain("invoices")?.sublevels?.map { it.label },
        )
        assertEquals(
            listOf(
                "Začať pracovný deň",
                "Ukončiť pracovný deň",
                "Pridať čas",
                "Mesačný report",
                "Nastavenie prestávky",
                "Vymazať mesiac",
            ),
            businessDomain("work-time")?.sublevels?.map { it.label },
        )
    }
}
