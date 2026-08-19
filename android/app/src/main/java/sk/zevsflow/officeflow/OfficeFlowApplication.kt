package sk.zevsflow.officeflow

import android.app.Application
import sk.zevsflow.officeflow.data.ContactRepository
import sk.zevsflow.officeflow.data.InvoiceRepository
import sk.zevsflow.officeflow.data.PdfRepository
import sk.zevsflow.officeflow.data.SessionCoordinator
import sk.zevsflow.officeflow.data.SessionRepository
import sk.zevsflow.officeflow.data.WorkspaceRepository
import sk.zevsflow.officeflow.data.WorkspaceSelectionStore
import sk.zevsflow.officeflow.network.OfficeFlowApiClient
import sk.zevsflow.officeflow.security.SecureSessionStore

class OfficeFlowApplication : Application() {
    lateinit var container: AppContainer
        private set

    override fun onCreate() {
        super.onCreate()
        container = AppContainer(this)
    }
}

class AppContainer(application: Application) {
    private val api = OfficeFlowApiClient(BuildConfig.OFFICEFLOW_API_BASE_URL)
    private val secureStore = SecureSessionStore(application)
    private val selectionStore = WorkspaceSelectionStore(application)
    private val coordinator = SessionCoordinator(secureStore, api)

    val sessionRepository = SessionRepository(api, secureStore, coordinator, selectionStore)
    val workspaceRepository = WorkspaceRepository(coordinator, api, selectionStore)
    val invoiceRepository = InvoiceRepository(coordinator, api)
    val contactRepository = ContactRepository(coordinator, api)
    val pdfRepository = PdfRepository(coordinator, api, application.cacheDir)
}
