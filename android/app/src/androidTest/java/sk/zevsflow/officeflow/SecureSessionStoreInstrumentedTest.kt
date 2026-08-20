package sk.zevsflow.officeflow

import androidx.test.core.app.ApplicationProvider
import java.io.File
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import sk.zevsflow.officeflow.data.SessionCredentials
import sk.zevsflow.officeflow.security.SecureSessionStore

class SecureSessionStoreInstrumentedTest {
    private val context get() = ApplicationProvider.getApplicationContext<android.content.Context>()
    private lateinit var store: SecureSessionStore

    @Before fun setUp() = runBlocking {
        store = SecureSessionStore(context)
        store.clear()
    }

    @After fun tearDown() = runBlocking { store.clear() }

    @Test fun encryptedCredentialBlobLivesOnlyInNoBackupStorage() = runBlocking {
        val credentials = SessionCredentials(
            accessToken = "ofacc_raw_secret",
            refreshToken = "ofref_raw_secret",
            accessExpiresAt = "2026-08-20T00:15:00+00:00",
            refreshExpiresAt = "2026-09-20T00:00:00+00:00",
        )

        store.replace(credentials)

        assertEquals(credentials, store.load())
        val file = File(context.noBackupFilesDir, "officeflow_session.enc")
        assertTrue(file.exists())
        assertTrue(file.canonicalPath.startsWith(context.noBackupFilesDir.canonicalPath))
        val bytes = file.readBytes().decodeToString()
        assertFalse(bytes.contains(credentials.accessToken))
        assertFalse(bytes.contains(credentials.refreshToken))
    }

    @Test fun corruptCiphertextFailsClosedAndDeletesMaterial() = runBlocking {
        val file = File(context.noBackupFilesDir, "officeflow_session.enc")
        file.writeBytes(byteArrayOf(1, 12, 1, 2, 3))

        assertNull(store.load())
        assertFalse(file.exists())
    }

    @Test fun logoutErasesCredentialBlob() = runBlocking {
        store.replace(
            SessionCredentials("a", "r", "2026-08-20T00:00:00Z", "2026-09-20T00:00:00Z")
        )
        store.clear()
        assertNull(store.load())
        assertFalse(File(context.noBackupFilesDir, "officeflow_session.enc").exists())
    }
}
