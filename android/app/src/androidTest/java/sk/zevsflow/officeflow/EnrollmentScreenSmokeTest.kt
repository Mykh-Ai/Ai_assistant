package sk.zevsflow.officeflow

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithText
import org.junit.Rule
import org.junit.Test

class EnrollmentScreenSmokeTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()

    @Test fun freshAppStartsAtAdministratorEnrollmentSurface() {
        compose.onNodeWithText("OfficeFlow").assertIsDisplayed()
        compose.onNodeWithText("Jednorazový pripájací kód").assertIsDisplayed()
        compose.onNodeWithText("Pripojiť").assertIsDisplayed()
        compose.onNodeWithText("Registrácia nie je verejná. Kód vydáva správca OfficeFlow.").assertIsDisplayed()
    }
}
