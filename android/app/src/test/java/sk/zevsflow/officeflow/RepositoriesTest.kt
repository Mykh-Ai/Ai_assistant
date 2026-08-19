package sk.zevsflow.officeflow

import kotlinx.coroutines.test.runTest
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.SocketPolicy
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import sk.zevsflow.officeflow.data.SessionCoordinator
import sk.zevsflow.officeflow.data.SessionCredentialStore
import sk.zevsflow.officeflow.data.SessionCredentials
import sk.zevsflow.officeflow.data.SessionRepository
import sk.zevsflow.officeflow.data.SessionResult
import sk.zevsflow.officeflow.data.WorkspaceChoice
import sk.zevsflow.officeflow.data.WorkspacePreferenceStore
import sk.zevsflow.officeflow.data.WorkspaceRepository
import sk.zevsflow.officeflow.network.OfficeFlowApiClient

class RepositoriesTest {
    private lateinit var server: MockWebServer
    private lateinit var api: OfficeFlowApiClient

    @Before fun startServer() {
        server = MockWebServer()
        server.start()
        api = OfficeFlowApiClient(server.url("/").toString())
    }

    @After fun stopServer() = server.shutdown()

    @Test fun validEnrollmentPersistsOnlyIssuedCredentialPair() = runTest {
        server.enqueue(sessionResponse("issued-access", "issued-refresh"))
        val credentials = FakeCredentialStore(null)
        val workspace = FakeWorkspaceStore(null)
        val repository = SessionRepository(
            api,
            credentials,
            SessionCoordinator(credentials, api),
            workspace,
        )

        val result = repository.enroll("ofenr_one_time_secret", "Pixel")

        assertEquals(SessionResult.Success(Unit), result)
        assertEquals("issued-access", credentials.value?.accessToken)
        assertEquals("issued-refresh", credentials.value?.refreshToken)
        assertFalse(credentials.value.toString().contains("ofenr_one_time_secret"))
        assertFalse(server.takeRequest().body.clone().readUtf8().contains("principal_id"))
    }

    @Test fun ambiguousEnrollmentIsNotRetriedOrPersisted() = runTest {
        server.enqueue(MockResponse().setSocketPolicy(SocketPolicy.DISCONNECT_AT_START))
        val credentials = FakeCredentialStore(null)
        val repository = SessionRepository(
            api,
            credentials,
            SessionCoordinator(credentials, api),
            FakeWorkspaceStore(null),
        )

        assertEquals(
            SessionResult.RefreshUncertain,
            repository.enroll("ofenr_uncertain", "Pixel"),
        )
        assertNull(credentials.value)
        assertEquals(1, server.requestCount)
    }

    @Test fun staleRememberedWorkspaceIsClearedAfterAuthoritativeServerList() = runTest {
        server.enqueue(
            jsonResponse(
                """{"workspaces":[{"workspace_id":"ws-a","display_name":"A","role":"owner"},{"workspace_id":"ws-b","display_name":"B","role":"member"}]}"""
            )
        )
        val credentials = FakeCredentialStore(session())
        val preference = FakeWorkspaceStore("ws-stale")
        val result = WorkspaceRepository(
            SessionCoordinator(credentials, api),
            api,
            preference,
        ).load()

        assertTrue(result is SessionResult.Success)
        val choice = (result as SessionResult.Success).value.second
        assertTrue(choice is WorkspaceChoice.PickerRequired)
        assertNull(preference.value)
        assertEquals("/v1/workspaces", server.takeRequest().path)
    }

    @Test fun logoutRevokesWhenPossibleAndAlwaysErasesLocalState() = runTest {
        server.enqueue(MockResponse().setResponseCode(204))
        val credentials = FakeCredentialStore(session())
        val preference = FakeWorkspaceStore("ws-a")
        val repository = SessionRepository(
            api,
            credentials,
            SessionCoordinator(credentials, api),
            preference,
        )

        assertTrue(repository.signOut())
        assertNull(credentials.value)
        assertNull(preference.value)
        assertEquals("DELETE", server.takeRequest().method)
    }

    @Test fun offlineLogoutErasesLocallyAndReportsUnconfirmedServerRevoke() = runTest {
        server.enqueue(MockResponse().setSocketPolicy(SocketPolicy.DISCONNECT_AT_START))
        val credentials = FakeCredentialStore(session())
        val preference = FakeWorkspaceStore("ws-a")
        val repository = SessionRepository(
            api,
            credentials,
            SessionCoordinator(credentials, api),
            preference,
        )

        assertFalse(repository.signOut())
        assertNull(credentials.value)
        assertNull(preference.value)
        assertEquals(1, server.requestCount)
    }

    private fun session() = SessionCredentials(
        "access", "refresh", "2026-08-20T00:00:00Z", "2026-09-20T00:00:00Z"
    )

    private fun sessionResponse(access: String, refresh: String) = jsonResponse(
        """{"session":{"access_token":"$access","refresh_token":"$refresh","access_expires_at":"2026-08-20T00:15:00Z","refresh_expires_at":"2026-09-20T00:00:00Z"}}"""
    )

    private fun jsonResponse(body: String) = MockResponse()
        .setResponseCode(200)
        .setHeader("Content-Type", "application/json")
        .setBody(body)

    private class FakeCredentialStore(initial: SessionCredentials?) : SessionCredentialStore {
        var value = initial
        override suspend fun load() = value
        override suspend fun replace(credentials: SessionCredentials) { value = credentials }
        override suspend fun clear() { value = null }
    }

    private class FakeWorkspaceStore(initial: String?) : WorkspacePreferenceStore {
        var value = initial
        override fun remembered() = value
        override fun remember(workspaceId: String) { value = workspaceId }
        override fun clear() { value = null }
    }
}
