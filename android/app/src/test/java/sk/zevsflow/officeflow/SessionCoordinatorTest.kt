package sk.zevsflow.officeflow

import java.util.concurrent.atomic.AtomicInteger
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.test.runTest
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import sk.zevsflow.officeflow.data.ApiResult
import sk.zevsflow.officeflow.data.SessionCoordinator
import sk.zevsflow.officeflow.data.SessionCredentialStore
import sk.zevsflow.officeflow.data.SessionCredentials
import sk.zevsflow.officeflow.data.SessionResult
import sk.zevsflow.officeflow.network.OfficeFlowApiClient

class SessionCoordinatorTest {
    private lateinit var server: MockWebServer
    private lateinit var api: OfficeFlowApiClient

    @Before fun startServer() {
        server = MockWebServer()
        server.start()
        api = OfficeFlowApiClient(server.url("/").toString())
    }

    @After fun stopServer() = server.shutdown()

    @Test fun freshInstallRequiresEnrollment() = runTest {
        val result = SessionCoordinator(FakeStore(null), api).authenticated<String> {
            error("request must not run without credentials")
        }
        assertSameResult(SessionResult.EnrollmentRequired, result)
    }

    @Test fun successfulRefreshAtomicallyReplacesCredentialsAndRetriesOnce() = runTest {
        val store = FakeStore(credentials("old-access", "old-refresh"))
        server.enqueue(sessionResponse("new-access", "new-refresh"))
        val calls = AtomicInteger()

        val result = SessionCoordinator(store, api).authenticated { token ->
            calls.incrementAndGet()
            if (token == "old-access") ApiResult.HttpFailure(401, "unauthorized")
            else ApiResult.Success("ok")
        }

        assertEquals(SessionResult.Success("ok"), result)
        assertEquals(2, calls.get())
        assertEquals("new-access", store.value?.accessToken)
        assertEquals("new-refresh", store.value?.refreshToken)
        assertEquals(1, server.requestCount)
        val refresh = server.takeRequest()
        assertEquals("/v1/session/refresh", refresh.path)
        assertFalse(refresh.body.readUtf8().contains("old-access"))
    }

    @Test fun concurrent401RequestsHaveOneRefreshOwner() = runTest {
        val store = FakeStore(credentials("old-access", "old-refresh"))
        server.enqueue(sessionResponse("new-access", "new-refresh"))
        val coordinator = SessionCoordinator(store, api)

        val results = List(8) {
            async {
                coordinator.authenticated { token ->
                    if (token == "old-access") ApiResult.HttpFailure(401, "unauthorized")
                    else ApiResult.Success(token)
                }
            }
        }.awaitAll()

        assertTrue(results.all { it == SessionResult.Success("new-access") })
        assertEquals(1, server.requestCount)
    }

    @Test fun requestWaitingForOwnerUsesAlreadyRefreshedToken() = runTest {
        val store = FakeStore(credentials("old-access", "old-refresh"))
        server.enqueue(sessionResponse("new-access", "new-refresh"))
        val coordinator = SessionCoordinator(store, api)

        val results = listOf(
            async { coordinator.authenticated(::protectedResult) },
            async { coordinator.authenticated(::protectedResult) },
        ).awaitAll()

        assertTrue(results.all { it == SessionResult.Success("new-access") })
        assertEquals(1, server.requestCount)
    }

    @Test fun definitiveRefresh401ErasesCredentials() = runTest {
        val store = FakeStore(credentials("old-access", "old-refresh"))
        server.enqueue(errorResponse(401, "unauthorized"))

        val result = SessionCoordinator(store, api).authenticated(::protectedResult)

        assertSameResult(SessionResult.EnrollmentRequired, result)
        assertNull(store.value)
        assertEquals(1, store.clearCount)
    }

    @Test fun temporaryBlockPreservesCredentialPairAndDoesNotRefresh() = runTest {
        val original = credentials("blocked-access", "blocked-refresh")
        val store = FakeStore(original)

        val result = SessionCoordinator(store, api).authenticated<String> {
            ApiResult.HttpFailure(423, "access_temporarily_unavailable")
        }

        assertSameResult(SessionResult.TemporarilyBlocked, result)
        assertEquals(original, store.value)
        assertEquals(0, server.requestCount)
    }

    @Test fun ambiguousRefreshIsPersistedAndNeverBlindlyReplayed() = runTest {
        val store = FakeStore(credentials("old-access", "old-refresh"))
        server.enqueue(MockResponse().setSocketPolicy(okhttp3.mockwebserver.SocketPolicy.DISCONNECT_AT_START))
        val coordinator = SessionCoordinator(store, api)

        val first = coordinator.authenticated(::protectedResult)
        val second = coordinator.authenticated(::protectedResult)

        assertSameResult(SessionResult.RefreshUncertain, first)
        assertSameResult(SessionResult.RefreshUncertain, second)
        assertTrue(store.value?.refreshUncertain == true)
        assertNotNull(store.value)
        assertEquals(1, server.requestCount)
        assertEquals(0, store.clearCount)
    }

    private fun protectedResult(token: String): ApiResult<String> =
        if (token == "old-access") ApiResult.HttpFailure(401, "unauthorized")
        else ApiResult.Success(token)

    private fun credentials(access: String, refresh: String) = SessionCredentials(
        accessToken = access,
        refreshToken = refresh,
        accessExpiresAt = "2026-08-20T00:15:00+00:00",
        refreshExpiresAt = "2026-09-20T00:00:00+00:00",
    )

    private fun sessionResponse(access: String, refresh: String) = MockResponse()
        .setResponseCode(200)
        .setHeader("Content-Type", "application/json")
        .setBody(
            """{"session":{"access_token":"$access","refresh_token":"$refresh","access_expires_at":"2026-08-20T00:15:00+00:00","refresh_expires_at":"2026-09-20T00:00:00+00:00","device_label":"Pixel"}}"""
        )

    private fun errorResponse(status: Int, code: String) = MockResponse()
        .setResponseCode(status)
        .setHeader("Content-Type", "application/json")
        .setBody("""{"error":{"code":"$code"}}"""
        )

    private fun assertSameResult(expected: SessionResult<Nothing>, actual: SessionResult<*>) {
        assertTrue("expected $expected, got $actual", expected === actual)
    }

    private class FakeStore(initial: SessionCredentials?) : SessionCredentialStore {
        var value = initial
        var clearCount = 0
        override suspend fun load(): SessionCredentials? = value
        override suspend fun replace(credentials: SessionCredentials) { value = credentials }
        override suspend fun clear() { value = null; clearCount += 1 }
    }
}
