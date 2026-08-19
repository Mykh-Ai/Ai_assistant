package sk.zevsflow.officeflow.data

import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import sk.zevsflow.officeflow.network.OfficeFlowApiClient

class SessionCoordinator(
    private val store: SessionCredentialStore,
    private val api: OfficeFlowApiClient,
) {
    private val refreshMutex = Mutex()

    suspend fun <T> authenticated(
        request: suspend (accessToken: String) -> ApiResult<T>,
    ): SessionResult<T> {
        val original = store.load() ?: return SessionResult.EnrollmentRequired
        return when (val first = request(original.accessToken)) {
            is ApiResult.Success -> SessionResult.Success(first.value)
            is ApiResult.HttpFailure -> when {
                first.status == 423 && first.code == "access_temporarily_unavailable" ->
                    SessionResult.TemporarilyBlocked
                first.status == 401 && original.refreshUncertain -> SessionResult.RefreshUncertain
                first.status == 401 -> refreshAndRetry(original, request)
                else -> SessionResult.Failure(first.code)
            }
            is ApiResult.NetworkFailure -> SessionResult.Failure("network_unavailable")
            is ApiResult.ProtocolFailure -> SessionResult.Failure(first.reason)
        }
    }

    private suspend fun <T> refreshAndRetry(
        rejected: SessionCredentials,
        request: suspend (accessToken: String) -> ApiResult<T>,
    ): SessionResult<T> = refreshMutex.withLock {
        val current = store.load() ?: return@withLock SessionResult.EnrollmentRequired
        if (current.accessToken != rejected.accessToken) {
            return@withLock mapRetry(request(current.accessToken))
        }

        when (val refresh = api.refresh(current.refreshToken)) {
            is ApiResult.Success -> {
                store.replace(refresh.value.session)
                mapRetry(request(refresh.value.session.accessToken))
            }
            is ApiResult.HttpFailure -> when {
                refresh.status == 423 && refresh.code == "access_temporarily_unavailable" ->
                    SessionResult.TemporarilyBlocked
                refresh.status == 401 -> {
                    store.clear()
                    SessionResult.EnrollmentRequired
                }
                else -> SessionResult.Failure(refresh.code)
            }
            is ApiResult.NetworkFailure -> {
                store.replace(current.copy(refreshUncertain = true))
                SessionResult.RefreshUncertain
            }
            is ApiResult.ProtocolFailure -> SessionResult.Failure(refresh.reason)
        }
    }

    private suspend fun <T> mapRetry(result: ApiResult<T>): SessionResult<T> = when (result) {
        is ApiResult.Success -> SessionResult.Success(result.value)
        is ApiResult.HttpFailure -> when {
            result.status == 423 && result.code == "access_temporarily_unavailable" ->
                SessionResult.TemporarilyBlocked
            result.status == 401 -> {
                store.clear()
                SessionResult.EnrollmentRequired
            }
            else -> SessionResult.Failure(result.code)
        }
        is ApiResult.NetworkFailure -> SessionResult.Failure("network_unavailable")
        is ApiResult.ProtocolFailure -> SessionResult.Failure(result.reason)
    }
}
