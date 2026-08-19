package sk.zevsflow.officeflow.data

import java.io.File
import java.util.UUID
import sk.zevsflow.officeflow.network.OfficeFlowApiClient

class SessionRepository(
    private val api: OfficeFlowApiClient,
    private val store: SessionCredentialStore,
    private val coordinator: SessionCoordinator,
    private val workspaceSelectionStore: WorkspacePreferenceStore,
) {
    suspend fun hasStoredSession(): Boolean = store.load() != null

    suspend fun enroll(secret: String, deviceLabel: String): SessionResult<Unit> {
        if (secret.isBlank() || secret.length > 160) return SessionResult.Failure("invalid_enrollment")
        return when (val result = api.exchangeEnrollment(secret.trim(), deviceLabel.take(80))) {
            is ApiResult.Success -> {
                store.replace(result.value.session)
                SessionResult.Success(Unit)
            }
            is ApiResult.HttpFailure -> SessionResult.Failure(result.code)
            is ApiResult.NetworkFailure -> SessionResult.RefreshUncertain
            is ApiResult.ProtocolFailure -> SessionResult.Failure(result.reason)
        }
    }

    suspend fun validate(): SessionResult<SessionMetadata> = coordinator.authenticated {
        when (val result = api.getSession(it)) {
            is ApiResult.Success -> ApiResult.Success(result.value.session)
            is ApiResult.HttpFailure -> result
            is ApiResult.NetworkFailure -> result
            is ApiResult.ProtocolFailure -> result
        }
    }

    suspend fun signOut(): Boolean {
        val credentials = store.load()
        val confirmed = if (credentials == null) true else {
            api.revoke(credentials.accessToken) is ApiResult.Success
        }
        store.clear()
        workspaceSelectionStore.clear()
        return confirmed
    }
}

class WorkspaceRepository(
    private val coordinator: SessionCoordinator,
    private val api: OfficeFlowApiClient,
    private val selection: WorkspacePreferenceStore,
) {
    suspend fun load(): SessionResult<Pair<List<Workspace>, WorkspaceChoice>> =
        coordinator.authenticated { token -> api.getWorkspaces(token) }.map { envelope ->
            val choice = WorkspaceSelectionPolicy.resolve(envelope.workspaces, selection.remembered())
            if (choice is WorkspaceChoice.PickerRequired && selection.remembered() != null) selection.clear()
            if (choice is WorkspaceChoice.Selected) selection.remember(choice.workspace.workspaceId)
            envelope.workspaces to choice
        }

    fun select(workspace: Workspace) = selection.remember(workspace.workspaceId)
    fun clear() = selection.clear()
}

class InvoiceRepository(
    private val coordinator: SessionCoordinator,
    private val api: OfficeFlowApiClient,
) {
    suspend fun list(workspaceId: String, offset: Int): SessionResult<InvoiceListEnvelope> =
        coordinator.authenticated { api.getInvoices(it, workspaceId, PAGE_SIZE, offset) }

    suspend fun detail(workspaceId: String, invoiceId: Long): SessionResult<InvoiceDetail> =
        coordinator.authenticated { token ->
            when (val result = api.getInvoice(token, workspaceId, invoiceId)) {
                is ApiResult.Success -> ApiResult.Success(result.value.invoice)
                is ApiResult.HttpFailure -> result
                is ApiResult.NetworkFailure -> result
                is ApiResult.ProtocolFailure -> result
            }
        }

    companion object { const val PAGE_SIZE = 50 }
}

class ContactRepository(
    private val coordinator: SessionCoordinator,
    private val api: OfficeFlowApiClient,
) {
    suspend fun list(workspaceId: String): SessionResult<List<Contact>> =
        coordinator.authenticated { token ->
            when (val result = api.getContacts(token, workspaceId)) {
                is ApiResult.Success -> ApiResult.Success(result.value.contacts)
                is ApiResult.HttpFailure -> result
                is ApiResult.NetworkFailure -> result
                is ApiResult.ProtocolFailure -> result
            }
        }
}

class PdfRepository(
    private val coordinator: SessionCoordinator,
    private val api: OfficeFlowApiClient,
    cacheDir: File,
) {
    private val directory = File(cacheDir, "officeflow-pdf")

    init { cleanup() }

    suspend fun download(workspaceId: String, invoiceId: Long): SessionResult<File> {
        val target = File(directory, "invoice-$invoiceId-${UUID.randomUUID()}.pdf")
        return coordinator.authenticated { token ->
            api.downloadInvoicePdf(token, workspaceId, invoiceId, target)
        }
    }

    fun release(file: File) {
        if (file.parentFile?.canonicalFile == directory.canonicalFile) file.delete()
    }

    fun cleanup() {
        directory.mkdirs()
        directory.listFiles()?.forEach { it.delete() }
    }
}

private inline fun <T, R> SessionResult<T>.map(transform: (T) -> R): SessionResult<R> = when (this) {
    is SessionResult.Success -> SessionResult.Success(transform(value))
    SessionResult.EnrollmentRequired -> SessionResult.EnrollmentRequired
    SessionResult.TemporarilyBlocked -> SessionResult.TemporarilyBlocked
    SessionResult.RefreshUncertain -> SessionResult.RefreshUncertain
    is SessionResult.Failure -> SessionResult.Failure(message)
}
