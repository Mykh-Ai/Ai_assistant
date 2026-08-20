package sk.zevsflow.officeflow.data

interface SessionCredentialStore {
    suspend fun load(): SessionCredentials?
    suspend fun replace(credentials: SessionCredentials)
    suspend fun clear()
}
