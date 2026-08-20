package sk.zevsflow.officeflow.ui

import android.graphics.Bitmap
import android.graphics.pdf.PdfRenderer
import android.os.ParcelFileDescriptor
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.consumeWindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.ScaffoldDefaults
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import java.io.File
import java.io.IOException
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import sk.zevsflow.officeflow.data.Contact
import sk.zevsflow.officeflow.data.InvoiceDetail
import sk.zevsflow.officeflow.data.InvoiceSummary
import sk.zevsflow.officeflow.data.Workspace

@Composable
fun OfficeFlowApp(viewModel: OfficeFlowViewModel) {
    val root by viewModel.root.collectAsState()
    when (val state = root) {
        RootState.Loading -> LoadingScreen(Modifier.windowInsetsPadding(WindowInsets.safeDrawing))
        is RootState.Enrollment -> EnrollmentScreen(state.message, viewModel::enroll)
        is RootState.WorkspacePicker -> WorkspacePickerScreen(
            state.workspaces,
            viewModel::chooseWorkspace,
            viewModel::signOut,
        )
        RootState.NoWorkspaces -> MessageScreen(
            "Nemáte dostupný žiadny firemný profil.",
            "Obnoviť" to viewModel::retry,
            "Odhlásiť" to viewModel::signOut,
        )
        RootState.TemporarilyBlocked -> MessageScreen(
            "Prístup je dočasne zablokovaný. Relácia zostala bezpečne uložená.",
            "Skúsiť znova" to viewModel::retry,
            "Odhlásiť lokálne" to viewModel::signOut,
        )
        RootState.RefreshUncertain -> MessageScreen(
            "Obnovenie relácie sa pre chybu siete nedá potvrdiť. Obnovovací token sa automaticky neopakuje.",
            "Overiť prístup" to viewModel::retry,
            "Odhlásiť lokálne" to viewModel::signOut,
        )
        is RootState.Ready -> ReadShell(state, viewModel)
    }
}

@Composable
private fun LoadingScreen(modifier: Modifier = Modifier) = Box(
    modifier.fillMaxSize(),
    contentAlignment = Alignment.Center,
) {
    CircularProgressIndicator()
}

@Composable
private fun EnrollmentScreen(message: String?, connect: (String) -> Unit) {
    var secret by remember { mutableStateOf("") }
    Column(
        Modifier
            .fillMaxSize()
            .windowInsetsPadding(WindowInsets.safeDrawing)
            .verticalScroll(rememberScrollState())
            .padding(24.dp),
        verticalArrangement = Arrangement.Center,
    ) {
        Text("OfficeFlow", style = MaterialTheme.typography.headlineLarge, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(8.dp))
        Text("Bezpečný read-only prístup pre kontrolovaný pilot")
        Spacer(Modifier.height(24.dp))
        OutlinedTextField(
            value = secret,
            onValueChange = { secret = it.take(160) },
            modifier = Modifier.fillMaxWidth(),
            label = { Text("Jednorazový pripájací kód") },
            visualTransformation = PasswordVisualTransformation(),
            singleLine = true,
        )
        message?.let {
            Spacer(Modifier.height(12.dp))
            Text(it, color = MaterialTheme.colorScheme.error)
        }
        Spacer(Modifier.height(16.dp))
        Button(
            onClick = {
                val submitted = secret
                secret = ""
                connect(submitted)
            },
            enabled = secret.isNotBlank(),
            modifier = Modifier.fillMaxWidth(),
        ) { Text("Pripojiť") }
        Spacer(Modifier.height(12.dp))
        Text("Registrácia nie je verejná. Kód vydáva správca OfficeFlow.")
    }
}

@Composable
private fun WorkspacePickerScreen(
    workspaces: List<Workspace>,
    choose: (Workspace) -> Unit,
    logout: () -> Unit,
) {
    Column(
        Modifier
            .fillMaxSize()
            .windowInsetsPadding(WindowInsets.safeDrawing)
            .padding(20.dp),
    ) {
        Text("Vyberte firemný profil", style = MaterialTheme.typography.headlineSmall)
        Spacer(Modifier.height(16.dp))
        LazyColumn(
            Modifier.weight(1f),
            contentPadding = PaddingValues(bottom = 16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            items(workspaces, key = { it.workspaceId }) { workspace ->
                Card(onClick = { choose(workspace) }, modifier = Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(16.dp)) {
                        Text(workspace.displayName, fontWeight = FontWeight.SemiBold)
                        Text("Rola: ${workspace.role}")
                    }
                }
            }
        }
        TextButton(onClick = logout, modifier = Modifier.fillMaxWidth()) { Text("Odhlásiť") }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ReadShell(root: RootState.Ready, viewModel: OfficeFlowViewModel) {
    val nav = rememberNavController()
    val backStack by nav.currentBackStackEntryAsState()
    val currentRoute = backStack?.destination?.route
    var confirmLogout by remember { mutableStateOf(false) }
    var showAccountMenu by remember { mutableStateOf(false) }
    val notice by viewModel.notice.collectAsState()
    val snackbar = remember { SnackbarHostState() }
    LaunchedEffect(notice) {
        notice?.let {
            snackbar.showSnackbar(it)
            viewModel.clearNotice()
        }
    }
    Scaffold(
        contentWindowInsets = ScaffoldDefaults.contentWindowInsets,
        topBar = {
            TopAppBar(
                title = { Text("OfficeFlow", maxLines = 1) },
                navigationIcon = {
                    if (currentRoute != null && currentRoute != HOME_ROUTE) {
                        IconButton(
                            onClick = { nav.popBackStack() },
                            modifier = Modifier.semantics { contentDescription = "Späť" },
                        ) { Text("‹", style = MaterialTheme.typography.headlineMedium) }
                    }
                },
                actions = {
                    Box {
                        TextButton(onClick = { showAccountMenu = true }) { Text("Menu") }
                        DropdownMenu(
                            expanded = showAccountMenu,
                            onDismissRequest = { showAccountMenu = false },
                        ) {
                            DropdownMenuItem(
                                text = { Text("Zmeniť profil") },
                                onClick = {
                                    showAccountMenu = false
                                    viewModel.showWorkspacePicker()
                                },
                            )
                            DropdownMenuItem(
                                text = { Text("Odhlásiť") },
                                onClick = {
                                    showAccountMenu = false
                                    confirmLogout = true
                                },
                            )
                        }
                    }
                },
            )
        },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        NavHost(
            navController = nav,
            startDestination = HOME_ROUTE,
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .consumeWindowInsets(padding),
        ) {
            composable(HOME_ROUTE) {
                HomeScreen(
                    workspace = root.workspace,
                    openDomain = { nav.navigate(domainRoute(it)) },
                    openVoiceChat = { nav.navigate("voice-chat-unavailable") },
                    changeProfile = viewModel::showWorkspacePicker,
                    logout = { confirmLogout = true },
                )
            }
            composable("domain/{domainId}") { entry ->
                val domain = businessDomain(entry.arguments?.getString("domainId"))
                if (domain == null) {
                    BoundedUnavailableScreen(
                        title = "Táto oblasť nie je dostupná.",
                        onBack = { nav.popBackStack() },
                        onHome = { nav.goHome() },
                    )
                } else {
                    DomainScreen(
                        domain = domain,
                        openSublevel = { sublevel ->
                            when (sublevel.availability) {
                                C1Availability.EXISTING_INVOICES -> nav.navigate(INVOICE_LIST_ROUTE)
                                C1Availability.EXISTING_CONTACTS -> nav.navigate(CONTACT_LIST_ROUTE)
                                C1Availability.UNAVAILABLE -> nav.navigate(
                                    unavailableRoute(domain.id, sublevel.id)
                                )
                            }
                        },
                        onHome = { nav.goHome() },
                    )
                }
            }
            composable("domain/{domainId}/unavailable/{sublevelId}") { entry ->
                val domainId = entry.arguments?.getString("domainId")
                val sublevelId = entry.arguments?.getString("sublevelId")
                val sublevel = businessSublevel(domainId, sublevelId)
                BoundedUnavailableScreen(
                    title = sublevel?.label ?: "Táto funkcia",
                    message = "Táto funkcia zatiaľ nie je dostupná v Android aplikácii. Momentálne ju môžete použiť v Telegram OfficeFlow.",
                    onBack = { nav.popBackStack() },
                    onHome = { nav.goHome() },
                )
            }
            composable("voice-chat-unavailable") {
                BoundedUnavailableScreen(
                    title = VOICE_CHAT_LABEL,
                    message = "Hlas a chat budú dostupné v ďalšej fáze.",
                    onBack = { nav.popBackStack() },
                    onHome = { nav.goHome() },
                )
            }
            composable(INVOICE_LIST_ROUTE) { InvoiceListScreen(root.workspace, nav, viewModel) }
            composable(CONTACT_LIST_ROUTE) { ContactsScreen(root.workspace, viewModel) }
            composable("invoice/{id}") { entry ->
                val id = entry.arguments?.getString("id")?.toLongOrNull()
                if (id == null) {
                    MessageScreen("Faktúra nie je dostupná.", "Späť" to { nav.popBackStack() })
                } else {
                    InvoiceDetailScreen(root.workspace, id, nav, viewModel)
                }
            }
            composable("invoice/{id}/pdf") { entry ->
                val id = entry.arguments?.getString("id")?.toLongOrNull()
                if (id == null) {
                    MessageScreen("PDF nie je dostupné.", "Späť" to { nav.popBackStack() })
                } else {
                    PdfScreen(id, nav, viewModel)
                }
            }
        }
    }
    if (confirmLogout) {
        AlertDialog(
            onDismissRequest = { confirmLogout = false },
            title = { Text("Odhlásiť sa?") },
            text = { Text("Lokálna relácia a výber profilu sa odstránia. Firemné údaje sa nemenia.") },
            confirmButton = {
                TextButton(onClick = {
                    confirmLogout = false
                    viewModel.signOut()
                }) { Text("Odhlásiť") }
            },
            dismissButton = { TextButton(onClick = { confirmLogout = false }) { Text("Zrušiť") } },
        )
    }
}

private fun NavHostController.goHome() {
    navigate(HOME_ROUTE) {
        popUpTo(HOME_ROUTE)
        launchSingleTop = true
    }
}

@Composable
internal fun HomeScreen(
    workspace: Workspace,
    openDomain: (String) -> Unit,
    openVoiceChat: () -> Unit,
    changeProfile: () -> Unit,
    logout: () -> Unit,
) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        item {
            Text("Domov", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
            Text("Vyberte oblasť, v ktorej chcete pokračovať.")
        }
        item { ActiveProfileCard(workspace, changeProfile, logout) }
        item { Text("Oblasti OfficeFlow", style = MaterialTheme.typography.titleLarge) }
        items(C1_BUSINESS_DOMAINS, key = BusinessDomain::id) { domain ->
            Card(onClick = { openDomain(domain.id) }, modifier = Modifier.fillMaxWidth()) {
                Column(Modifier.padding(14.dp)) {
                    Text(domain.label, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                    Text("Zobraziť možnosti", style = MaterialTheme.typography.bodyMedium)
                }
            }
        }
        item {
            Spacer(Modifier.height(6.dp))
            Text("Univerzálny kanál", style = MaterialTheme.typography.titleMedium)
            Spacer(Modifier.height(8.dp))
            OutlinedCard(onClick = openVoiceChat, modifier = Modifier.fillMaxWidth()) {
                Column(Modifier.padding(14.dp)) {
                    Text(VOICE_CHAT_LABEL, fontWeight = FontWeight.SemiBold)
                    Text("Hlas a chat budú dostupné v ďalšej fáze.")
                }
            }
        }
    }
}

@Composable
private fun ActiveProfileCard(workspace: Workspace, changeProfile: () -> Unit, logout: () -> Unit) {
    OutlinedCard(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp)) {
            Text("Aktívny profil", style = MaterialTheme.typography.labelLarge)
            Text(workspace.displayName, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Text("Rola: ${workspace.role}", style = MaterialTheme.typography.bodySmall)
            Spacer(Modifier.height(12.dp))
            OutlinedButton(onClick = changeProfile, modifier = Modifier.fillMaxWidth()) { Text("Zmeniť profil") }
            TextButton(onClick = logout, modifier = Modifier.fillMaxWidth()) { Text("Odhlásiť") }
        }
    }
}

@Composable
private fun DomainScreen(domain: BusinessDomain, openSublevel: (BusinessSublevel) -> Unit, onHome: () -> Unit) {
    if (domain.sublevels.isEmpty()) {
        BoundedUnavailableScreen(
            title = domain.label,
            message = "Táto informačná oblasť zatiaľ nie je dostupná v Android aplikácii.",
            onBack = onHome,
            onHome = onHome,
        )
        return
    }
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        item { Text(domain.label, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold) }
        items(domain.sublevels, key = BusinessSublevel::id) { sublevel ->
            Card(onClick = { openSublevel(sublevel) }, modifier = Modifier.fillMaxWidth()) {
                Column(Modifier.padding(14.dp)) {
                    Text(sublevel.label, fontWeight = FontWeight.SemiBold)
                    Text(
                        if (sublevel.availability == C1Availability.UNAVAILABLE) "V Androide zatiaľ nedostupné"
                        else "Dostupné v read-only režime",
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
            }
        }
        item { TextButton(onClick = onHome, modifier = Modifier.fillMaxWidth()) { Text("Domov") } }
    }
}

@Composable
private fun BoundedUnavailableScreen(
    title: String,
    message: String = "Táto funkcia zatiaľ nie je dostupná v Android aplikácii.",
    onBack: () -> Unit,
    onHome: () -> Unit,
) {
    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(24.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(title, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.SemiBold)
        Spacer(Modifier.height(12.dp))
        Text(message)
        Spacer(Modifier.height(20.dp))
        OutlinedButton(onClick = onBack, modifier = Modifier.fillMaxWidth()) { Text("Späť") }
        TextButton(onClick = onHome, modifier = Modifier.fillMaxWidth()) { Text("Domov") }
    }
}

@Composable
private fun InvoiceListScreen(workspace: Workspace, nav: NavHostController, viewModel: OfficeFlowViewModel) {
    val state by viewModel.invoices.collectAsState()
    LaunchedEffect(workspace.workspaceId) { viewModel.loadInvoices() }
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(horizontal = 16.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        item {
            Text("Existujúce faktúry", style = MaterialTheme.typography.headlineSmall)
            Text("Profil: ${workspace.displayName}", style = MaterialTheme.typography.labelMedium)
        }
        if (state.loading && state.items.isEmpty()) {
            item { LoadingScreen(Modifier.height(160.dp)) }
        } else {
            items(state.items, key = { it.id }) { invoice ->
                InvoiceCard(invoice) { nav.navigate("invoice/${invoice.id}") }
            }
            item {
                state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                if (!state.endReached) {
                    OutlinedButton(
                        onClick = { viewModel.loadInvoices(reset = false) },
                        enabled = !state.loading,
                        modifier = Modifier.fillMaxWidth(),
                    ) { Text(if (state.loading) "Načítavam…" else "Načítať ďalšie") }
                }
            }
        }
    }
}

@Composable
internal fun InvoiceCard(invoice: InvoiceSummary, open: () -> Unit) {
    Card(onClick = open, modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp)) {
            Text("Faktúra ${invoice.invoiceNumber}", fontWeight = FontWeight.SemiBold)
            Text(invoice.customer?.name ?: "Odberateľ neuvedený")
            Text("${invoice.issueDate} · splatnosť ${invoice.dueDate}")
            Text("${money(invoice.totalAmount)} ${invoice.currency} · ${invoice.status}")
        }
    }
}

@Composable
private fun InvoiceDetailScreen(workspace: Workspace, invoiceId: Long, nav: NavHostController, viewModel: OfficeFlowViewModel) {
    val detail by viewModel.detail.collectAsState()
    LaunchedEffect(invoiceId, workspace.workspaceId) { viewModel.loadInvoice(invoiceId) }
    when (val state = detail) {
        DetailState.Idle, DetailState.Loading -> LoadingScreen()
        is DetailState.Error -> MessageScreen(
            state.failure.message,
            "Skúsiť znova" to { viewModel.loadInvoice(invoiceId) },
            "Späť" to { nav.popBackStack() },
        )
        is DetailState.Ready -> InvoiceDetailContent(state.invoice) { nav.navigate("invoice/$invoiceId/pdf") }
    }
}

@Composable
internal fun InvoiceDetailContent(invoice: InvoiceDetail, openPdf: () -> Unit) {
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp)) {
        Text("Faktúra ${invoice.invoiceNumber}", style = MaterialTheme.typography.headlineSmall)
        Text(invoice.customer?.name ?: "Odberateľ neuvedený")
        Spacer(Modifier.height(12.dp))
        LabelValue("Vystavenie", invoice.issueDate)
        LabelValue("Dodanie", invoice.deliveryDate)
        LabelValue("Splatnosť", "${invoice.dueDate} (${invoice.dueDays} dní)")
        LabelValue("Stav", invoice.status)
        LabelValue("Suma", "${money(invoice.totalAmount)} ${invoice.currency}")
        Spacer(Modifier.height(18.dp))
        Text("Položky", fontWeight = FontWeight.SemiBold)
        invoice.items.forEach { item ->
            HorizontalDivider(Modifier.padding(vertical = 8.dp))
            Text(item.description, fontWeight = FontWeight.Medium)
            item.detail?.takeIf(String::isNotBlank)?.let { Text(it) }
            val unit = item.unit?.takeIf(String::isNotBlank) ?: "jednotka neuvedená"
            Text("${item.quantity} $unit")
            Text("${money(item.unitPrice)} × ${item.quantity} = ${money(item.totalPrice)}")
        }
        Spacer(Modifier.height(20.dp))
        Button(onClick = openPdf, modifier = Modifier.fillMaxWidth()) { Text("Zobraziť PDF") }
    }
}

@Composable
private fun ContactsScreen(workspace: Workspace, viewModel: OfficeFlowViewModel) {
    val state by viewModel.contacts.collectAsState()
    LaunchedEffect(workspace.workspaceId) { viewModel.loadContacts() }
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(horizontal = 16.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        item {
            Text("Existujúce kontakty", style = MaterialTheme.typography.headlineSmall)
            Text("Profil: ${workspace.displayName}", style = MaterialTheme.typography.labelMedium)
        }
        if (state.loading) {
            item { LoadingScreen(Modifier.height(160.dp)) }
        } else {
            items(state.items, key = Contact::id) { contact -> ContactCard(contact) }
            item {
                if (state.items.isEmpty() && state.error == null) Text("Žiadne kontakty.")
                state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            }
        }
    }
}

@Composable
internal fun ContactCard(contact: Contact) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp)) {
            Text(contact.name, fontWeight = FontWeight.SemiBold)
            ContactLine("IČO", contact.ico)
            ContactLine("DIČ", contact.dic)
            ContactLine("IČ DPH", contact.icDph)
            ContactLine("Adresa", contact.address)
            ContactLine("Email", contact.email)
            ContactLine("IBAN", contact.iban)
            ContactLine("Kontaktná osoba", contact.contactPerson)
        }
    }
}

@Composable
private fun PdfScreen(invoiceId: Long, nav: NavHostController, viewModel: OfficeFlowViewModel) {
    val file by viewModel.pdf.collectAsState()
    LaunchedEffect(invoiceId) { viewModel.loadPdf(invoiceId) }
    DisposableEffect(invoiceId) { onDispose(viewModel::releasePdf) }
    when (val state = file) {
        PdfUiState.Idle, PdfUiState.Loading -> LoadingScreen()
        is PdfUiState.Error -> MessageScreen(
            state.failure.message,
            "Skúsiť znova" to { viewModel.loadPdf(invoiceId) },
            "Späť" to { nav.popBackStack() },
        )
        is PdfUiState.Ready -> PdfPage(
            state.file,
            retry = { viewModel.loadPdf(invoiceId) },
            back = { nav.popBackStack() },
        )
    }
}

@Composable
private fun PdfPage(file: File, retry: () -> Unit, back: () -> Unit) {
    var pageIndex by remember(file) { mutableStateOf(0) }
    val rendered by produceState<PdfRenderState>(
        initialValue = PdfRenderState.Loading,
        file,
        pageIndex,
    ) {
        value = try {
            withContext(Dispatchers.IO) {
                ParcelFileDescriptor.open(file, ParcelFileDescriptor.MODE_READ_ONLY).use { descriptor ->
                    PdfRenderer(descriptor).use { renderer ->
                        if (renderer.pageCount < 1) return@use PdfRenderState.Error
                        val boundedIndex = pageIndex.coerceIn(0, renderer.pageCount - 1)
                        renderer.openPage(boundedIndex).use { page ->
                            val scale = minOf(
                                2f,
                                MAX_PDF_RENDER_DIMENSION.toFloat() / page.width.coerceAtLeast(1),
                                MAX_PDF_RENDER_DIMENSION.toFloat() / page.height.coerceAtLeast(1),
                            )
                            val bitmap = Bitmap.createBitmap(
                                (page.width * scale).toInt().coerceAtLeast(1),
                                (page.height * scale).toInt().coerceAtLeast(1),
                                Bitmap.Config.ARGB_8888,
                            ).also {
                                page.render(it, null, null, PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY)
                            }
                            PdfRenderState.Ready(
                                RenderedPdfPage(bitmap, boundedIndex, renderer.pageCount)
                            )
                        }
                    }
                }
            }
        } catch (_: IOException) {
            PdfRenderState.Error
        } catch (error: RuntimeException) {
            if (error is CancellationException) throw error
            PdfRenderState.Error
        }
    }
    val ready = rendered as? PdfRenderState.Ready
    DisposableEffect(ready?.page?.bitmap) { onDispose { ready?.page?.bitmap?.recycle() } }
    Column(Modifier.fillMaxSize().padding(8.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        when (val state = rendered) {
            PdfRenderState.Loading -> LoadingScreen()
            PdfRenderState.Error -> MessageScreen(
                pdfRenderingFailure().message,
                "Skúsiť znova" to retry,
                "Späť" to back,
            )
            is PdfRenderState.Ready -> {
                val page = state.page
                Image(
                    page.bitmap.asImageBitmap(),
                    contentDescription = "Strana ${page.index + 1} PDF",
                    modifier = Modifier.weight(1f).fillMaxWidth(),
                )
                Row(
                    Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    TextButton(onClick = { pageIndex -= 1 }, enabled = page.index > 0) {
                        Text("Predchádzajúca")
                    }
                    Text("${page.index + 1} / ${page.count}")
                    TextButton(onClick = { pageIndex += 1 }, enabled = page.index + 1 < page.count) {
                        Text("Ďalšia")
                    }
                }
            }
        }
    }
}

private sealed interface PdfRenderState {
    data object Loading : PdfRenderState
    data object Error : PdfRenderState
    data class Ready(val page: RenderedPdfPage) : PdfRenderState
}

private data class RenderedPdfPage(val bitmap: Bitmap, val index: Int, val count: Int)
private const val MAX_PDF_RENDER_DIMENSION = 4096

@Composable
private fun LabelValue(label: String, value: String) {
    Column(Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
        Text(label, style = MaterialTheme.typography.labelMedium)
        Text(value, fontWeight = FontWeight.Medium)
    }
}

@Composable
private fun ContactLine(label: String, value: String?) {
    value?.takeIf(String::isNotBlank)?.let {
        Column(Modifier.fillMaxWidth().padding(top = 4.dp)) {
            Text(label, style = MaterialTheme.typography.labelSmall)
            Text(it)
        }
    }
}

@Composable
internal fun MessageScreen(message: String, vararg actions: Pair<String, () -> Unit>) {
    Column(
        Modifier
            .fillMaxSize()
            .windowInsetsPadding(WindowInsets.safeDrawing)
            .verticalScroll(rememberScrollState())
            .padding(24.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(message)
        actions.forEach { (label, action) ->
            Spacer(Modifier.height(10.dp))
            OutlinedButton(onClick = action, modifier = Modifier.fillMaxWidth()) { Text(label) }
        }
    }
}

private fun money(value: Double): String = "%.2f".format(java.util.Locale.US, value)
