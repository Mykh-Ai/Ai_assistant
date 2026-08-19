package sk.zevsflow.officeflow.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import java.io.File
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import sk.zevsflow.officeflow.AppContainer
import sk.zevsflow.officeflow.data.Contact
import sk.zevsflow.officeflow.data.InvoiceDetail
import sk.zevsflow.officeflow.data.InvoiceRepository
import sk.zevsflow.officeflow.data.InvoiceSummary
import sk.zevsflow.officeflow.data.SessionResult
import sk.zevsflow.officeflow.data.Workspace
import sk.zevsflow.officeflow.data.WorkspaceChoice

sealed interface RootState {
    data object Loading : RootState
    data class Enrollment(val message: String? = null) : RootState
    data class WorkspacePicker(val workspaces: List<Workspace>) : RootState
    data object NoWorkspaces : RootState
    data class Ready(val workspace: Workspace, val workspaces: List<Workspace>) : RootState
    data object TemporarilyBlocked : RootState
    data object RefreshUncertain : RootState
}

data class InvoiceListState(
    val loading: Boolean = false,
    val items: List<InvoiceSummary> = emptyList(),
    val nextOffset: Int = 0,
    val endReached: Boolean = false,
    val error: String? = null,
)

data class ContactsState(
    val loading: Boolean = false,
    val items: List<Contact> = emptyList(),
    val error: String? = null,
)

sealed interface DetailState {
    data object Idle : DetailState
    data object Loading : DetailState
    data class Ready(val invoice: InvoiceDetail) : DetailState
    data class Error(val message: String) : DetailState
}

sealed interface PdfUiState {
    data object Idle : PdfUiState
    data object Loading : PdfUiState
    data class Ready(val file: File) : PdfUiState
    data class Error(val message: String) : PdfUiState
}

class OfficeFlowViewModel(private val container: AppContainer) : ViewModel() {
    private val _root = MutableStateFlow<RootState>(RootState.Loading)
    val root: StateFlow<RootState> = _root.asStateFlow()

    private val _invoices = MutableStateFlow(InvoiceListState())
    val invoices: StateFlow<InvoiceListState> = _invoices.asStateFlow()

    private val _contacts = MutableStateFlow(ContactsState())
    val contacts: StateFlow<ContactsState> = _contacts.asStateFlow()

    private val _detail = MutableStateFlow<DetailState>(DetailState.Idle)
    val detail: StateFlow<DetailState> = _detail.asStateFlow()

    private val _pdf = MutableStateFlow<PdfUiState>(PdfUiState.Idle)
    val pdf: StateFlow<PdfUiState> = _pdf.asStateFlow()

    private val _notice = MutableStateFlow<String?>(null)
    val notice: StateFlow<String?> = _notice.asStateFlow()

    init { initialize() }

    fun initialize() {
        viewModelScope.launch {
            _root.value = RootState.Loading
            if (!container.sessionRepository.hasStoredSession()) {
                _root.value = RootState.Enrollment()
                return@launch
            }
            when (container.sessionRepository.validate()) {
                is SessionResult.Success -> loadWorkspaces()
                SessionResult.EnrollmentRequired -> _root.value = RootState.Enrollment("Relácia už nie je platná.")
                SessionResult.TemporarilyBlocked -> _root.value = RootState.TemporarilyBlocked
                SessionResult.RefreshUncertain -> _root.value = RootState.RefreshUncertain
                is SessionResult.Failure -> loadWorkspaces()
            }
        }
    }

    fun enroll(secret: String) {
        viewModelScope.launch {
            _root.value = RootState.Loading
            when (container.sessionRepository.enroll(secret, "OfficeFlow Android")) {
                is SessionResult.Success -> loadWorkspaces()
                SessionResult.RefreshUncertain -> _root.value = RootState.Enrollment(
                    "Výsledok pripojenia sa pre chybu siete nedá potvrdiť. Kód neopakujte automaticky; požiadajte správcu o kontrolu."
                )
                else -> _root.value = RootState.Enrollment("Kód je neplatný, použitý alebo exspirovaný.")
            }
        }
    }

    fun retry() = initialize()

    private suspend fun loadWorkspaces() {
        when (val result = container.workspaceRepository.load()) {
            is SessionResult.Success -> {
                val (workspaces, choice) = result.value
                _root.value = when (choice) {
                    WorkspaceChoice.Empty -> RootState.NoWorkspaces
                    is WorkspaceChoice.PickerRequired -> RootState.WorkspacePicker(choice.workspaces)
                    is WorkspaceChoice.Selected -> RootState.Ready(choice.workspace, workspaces)
                }
            }
            else -> handleSessionResult(result)
        }
    }

    fun chooseWorkspace(workspace: Workspace) {
        container.workspaceRepository.select(workspace)
        val all = when (val state = _root.value) {
            is RootState.Ready -> state.workspaces
            is RootState.WorkspacePicker -> state.workspaces
            else -> listOf(workspace)
        }
        _root.value = RootState.Ready(workspace, all)
        clearBusinessState()
    }

    fun showWorkspacePicker() {
        val state = _root.value as? RootState.Ready ?: return
        _root.value = RootState.WorkspacePicker(state.workspaces)
    }

    fun loadInvoices(reset: Boolean = true) {
        viewModelScope.launch {
            val workspace = currentWorkspace() ?: return@launch
            val old = _invoices.value
            if (old.loading || (!reset && old.endReached)) return@launch
            val offset = if (reset) 0 else old.nextOffset
            _invoices.value = if (reset) InvoiceListState(loading = true) else old.copy(loading = true, error = null)
            when (val result = container.invoiceRepository.list(workspace.workspaceId, offset)) {
                is SessionResult.Success -> {
                    val page = result.value.invoices
                    val combined = if (reset) page else (old.items + page).distinctBy { it.id }
                    _invoices.value = InvoiceListState(
                        items = combined,
                        nextOffset = offset + page.size,
                        endReached = page.size < InvoiceRepository.PAGE_SIZE,
                    )
                }
                else -> {
                    handleSessionResult(result)
                    _invoices.value = old.copy(loading = false, error = messageFor(result))
                }
            }
        }
    }

    fun loadInvoice(invoiceId: Long) {
        viewModelScope.launch {
            _detail.value = DetailState.Loading
            val workspace = currentWorkspace() ?: return@launch
            when (val result = container.invoiceRepository.detail(workspace.workspaceId, invoiceId)) {
                is SessionResult.Success -> _detail.value = DetailState.Ready(result.value)
                else -> {
                    handleSessionResult(result)
                    _detail.value = DetailState.Error(messageFor(result))
                }
            }
        }
    }

    fun loadContacts() {
        viewModelScope.launch {
            val workspace = currentWorkspace() ?: return@launch
            _contacts.value = ContactsState(loading = true)
            when (val result = container.contactRepository.list(workspace.workspaceId)) {
                is SessionResult.Success -> _contacts.value = ContactsState(items = result.value)
                else -> {
                    handleSessionResult(result)
                    _contacts.value = ContactsState(error = messageFor(result))
                }
            }
        }
    }

    fun loadPdf(invoiceId: Long) {
        viewModelScope.launch {
            releasePdf()
            _pdf.value = PdfUiState.Loading
            val workspace = currentWorkspace() ?: return@launch
            when (val result = container.pdfRepository.download(workspace.workspaceId, invoiceId)) {
                is SessionResult.Success -> _pdf.value = PdfUiState.Ready(result.value)
                else -> {
                    handleSessionResult(result)
                    _pdf.value = PdfUiState.Error("PDF nie je dostupné.")
                }
            }
        }
    }

    fun releasePdf() {
        (_pdf.value as? PdfUiState.Ready)?.file?.let(container.pdfRepository::release)
        _pdf.value = PdfUiState.Idle
    }

    fun signOut() {
        viewModelScope.launch {
            val confirmed = container.sessionRepository.signOut()
            clearBusinessState()
            _root.value = RootState.Enrollment(
                if (confirmed) "Boli ste odhlásený."
                else "Lokálne odhlásenie je dokončené, ale zrušenie relácie na serveri sa nepodarilo potvrdiť."
            )
        }
    }

    fun clearNotice() { _notice.value = null }

    private fun currentWorkspace(): Workspace? = (_root.value as? RootState.Ready)?.workspace

    private fun clearBusinessState() {
        _invoices.value = InvoiceListState()
        _contacts.value = ContactsState()
        _detail.value = DetailState.Idle
        releasePdf()
    }

    private fun handleSessionResult(result: SessionResult<*>) {
        when (result) {
            SessionResult.EnrollmentRequired -> _root.value = RootState.Enrollment("Relácia už nie je platná.")
            SessionResult.TemporarilyBlocked -> _root.value = RootState.TemporarilyBlocked
            SessionResult.RefreshUncertain -> _root.value = RootState.RefreshUncertain
            else -> Unit
        }
    }

    private fun messageFor(result: SessionResult<*>): String = when (result) {
        SessionResult.EnrollmentRequired -> "Vyžaduje sa nové pripojenie."
        SessionResult.TemporarilyBlocked -> "Prístup je dočasne zablokovaný."
        SessionResult.RefreshUncertain -> "Obnovenie relácie sa nedá bezpečne potvrdiť."
        is SessionResult.Failure -> when (result.message) {
            "not_found", "workspace_not_found" -> "Záznam nie je dostupný."
            else -> "Požiadavku sa nepodarilo dokončiť."
        }
        is SessionResult.Success -> ""
    }

    override fun onCleared() {
        releasePdf()
        super.onCleared()
    }
}
