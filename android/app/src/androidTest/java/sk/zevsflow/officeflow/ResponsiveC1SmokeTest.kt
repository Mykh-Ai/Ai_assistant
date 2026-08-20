package sk.zevsflow.officeflow

import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import org.junit.Rule
import org.junit.Test
import sk.zevsflow.officeflow.data.Contact
import sk.zevsflow.officeflow.data.InvoiceDetail
import sk.zevsflow.officeflow.data.InvoiceItem
import sk.zevsflow.officeflow.data.Workspace
import sk.zevsflow.officeflow.ui.ContactCard
import sk.zevsflow.officeflow.ui.HomeScreen
import sk.zevsflow.officeflow.ui.InvoiceDetailContent
import sk.zevsflow.officeflow.ui.OfficeFlowTheme

class ResponsiveC1SmokeTest {
    @get:Rule val compose = createComposeRule()

    @Test fun homeRemainsReachableAtOnePointThreeFontScale() = assertHomeAtFontScale(1.3f)

    @Test fun homeRemainsReachableAtOnePointFiveFontScale() = assertHomeAtFontScale(1.5f)

    @Test fun homeRemainsReachableAtTwoFontScale() = assertHomeAtFontScale(2f)

    private fun assertHomeAtFontScale(fontScale: Float) {
        compose.setContent {
            CompositionLocalProvider(LocalDensity provides Density(density = 1f, fontScale = fontScale)) {
                OfficeFlowTheme {
                    HomeScreen(
                        workspace = Workspace(
                            "ws-a",
                            "Veľmi dlhý názov overeného firemného profilu pre pilotné zariadenie",
                            "owner",
                        ),
                        openDomain = {},
                        openVoiceChat = {},
                        changeProfile = {},
                        logout = {},
                    )
                }
            }
        }

        compose.onNodeWithText("Domov").assertIsDisplayed()
        compose.onNodeWithText("InfoHelp").performScrollTo().assertIsDisplayed()
        compose.onNodeWithText("Hlas / Chat").performScrollTo().assertIsDisplayed()
    }

    @Test fun productionShapedDetailWithNullableUnitRemainsScrollableAtLargeFontScale() {
        compose.setContent {
            CompositionLocalProvider(LocalDensity provides Density(density = 1f, fontScale = 2f)) {
                OfficeFlowTheme {
                    InvoiceDetailContent(
                        invoice = InvoiceDetail(
                            id = 7,
                            invoiceNumber = "20260007",
                            issueDate = "2026-08-01",
                            deliveryDate = "2026-08-01",
                            dueDate = "2026-08-15",
                            dueDays = 14,
                            totalAmount = 100.0,
                            currency = "EUR",
                            status = "created",
                            items = listOf(
                                InvoiceItem(
                                    description = "Veľmi dlhý popis práce pre overenie zalamovania textu",
                                    detail = "Doplňujúci detail bez citlivých údajov",
                                    quantity = 2.0,
                                    unit = null,
                                    unitPrice = 50.0,
                                    totalPrice = 100.0,
                                )
                            ),
                        ),
                        openPdf = {},
                    )
                }
            }
        }

        compose.onNodeWithText("jednotka neuvedená", substring = true).performScrollTo().assertIsDisplayed()
        compose.onNodeWithText("Zobraziť PDF").performScrollTo().assertIsDisplayed()
    }

    @Test fun longContactFieldsRemainReachableAtLargeFontScale() {
        compose.setContent {
            CompositionLocalProvider(LocalDensity provides Density(density = 1f, fontScale = 2f)) {
                OfficeFlowTheme {
                    LazyColumn(contentPadding = PaddingValues(16.dp)) {
                        item {
                            ContactCard(
                                Contact(
                                    id = 4,
                                    name = "Veľmi dlhý názov kontaktu, ktorý sa musí bezpečne zalomiť",
                                    address = "Veľmi dlhá adresa bez súkromných produkčných údajov",
                                    email = "pilot-contact-with-long-name@example.invalid",
                                    iban = "SK00 0000 0000 0000 0000 0000",
                                    contactPerson = "Dlhé meno kontaktnej osoby pre responsive kontrolu",
                                )
                            )
                        }
                    }
                }
            }
        }

        compose.onNodeWithText("Veľmi dlhý názov kontaktu", substring = true).assertIsDisplayed()
        compose.onNodeWithText("SK00 0000 0000 0000 0000 0000").performScrollTo().assertIsDisplayed()
    }
}
