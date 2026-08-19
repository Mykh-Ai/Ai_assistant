package sk.zevsflow.officeflow.ui

import android.graphics.Bitmap
import android.graphics.pdf.PdfRenderer
import android.os.ParcelFileDescriptor
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import java.io.File
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
        RootState.Loading -> LoadingScreen()
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
private fun LoadingScreen() = Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
    CircularProgressIndicator()
}

@Composable
private fun EnrollmentScreen(message: String?, connect: (String) -> Unit) {
    var secret by remember { mutableStateOf("") }
    Column(
        Modifier.fillMaxSize().padding(24.dp),
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
    Column(Modifier.fillMaxSize().padding(20.dp)) {
        Text("Vyberte firemný profil", style = MaterialTheme.typography.headlineSmall)
        Spacer(Modifier.height(16.dp))
        LazyColumn(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            items(workspaces, key = { it.workspaceId }) { workspace ->
                Card(onClick = { choose(workspace) }, modifier = Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(16.dp)) {
                        Text(workspace.displayName, fontWeight = FontWeight.SemiBold)
                        Text("Rola: ${workspace.role}")
                    }
                }
            }
        }
        TextButton(onClick = logout) { Text("Odhlásiť") }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ReadShell(root: RootState.Ready, viewModel: OfficeFlowViewModel) {
    val nav = rememberNavController()
    var confirmLogout by remember { mutableStateOf(false) }
    val notice by viewModel.notice.collectAsState()
    val snackbar = remember { SnackbarHostState() }
    LaunchedEffect(notice) {
        notice?.let { snackbar.showSnackbar(it); viewModel.clearNotice() }
    }
    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("OfficeFlow")
                        Text(root.workspace.displayName, style = MaterialTheme.typography.labelMedium)
                    }
                },
                actions = {
                    TextButton(onClick = viewModel::showWorkspacePicker) { Text("Profil") }
                    TextButton(onClick = { confirmLogout = true }) { Text("Odhlásiť") }
                },
            )
        },
        bottomBar = {
            NavigationBar {
                NavigationBarItem(
                    selected = currentRoute(nav) == "invoices",
                    onClick = { nav.navigate("invoices") { launchSingleTop = true } },
                    icon = { Text("F") },
                    label = { Text("Faktúry") },
                )
                NavigationBarItem(
                    selected = currentRoute(nav) == "contacts",
                    onClick = { nav.navigate("contacts") { launchSingleTop = true } },
                    icon = { Text("K") },
                    label = { Text("Kontakty") },
                )
            }
        },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        NavHost(nav, startDestination = "invoices", modifier = Modifier.padding(padding)) {
            composable("invoices") { InvoiceListScreen(root.workspace, nav, viewModel) }
            composable("contacts") { ContactsScreen(root.workspace, viewModel) }
            composable("invoice/{id}") { entry ->
                val id = entry.arguments?.getString("id")?.toLongOrNull()
                if (id == null) MessageScreen("Faktúra nie je dostupná.")
                else InvoiceDetailScreen(root.workspace, id, nav, viewModel)
            }
            composable("invoice/{id}/pdf") { entry ->
                val id = entry.arguments?.getString("id")?.toLongOrNull()
                if (id == null) MessageScreen("PDF nie je dostupné.")
                else PdfScreen(id, viewModel)
            }
        }
    }
    if (confirmLogout) {
        AlertDialog(
            onDismissRequest = { confirmLogout = false },
            title = { Text("Odhlásiť sa?") },
            text = { Text("Lokálna relácia a výber profilu sa odstránia. Firemné údaje sa nemenia.") },
            confirmButton = { TextButton(onClick = { confirmLogout = false; viewModel.signOut() }) { Text("Odhlásiť") } },
            dismissButton = { TextButton(onClick = { confirmLogout = false }) { Text("Zrušiť") } },
        )
    }
}

@Composable
private fun currentRoute(nav: NavHostController): String? =
    nav.currentBackStackEntryFlow.collectAsState(initial = nav.currentBackStackEntry).value?.destination?.route

@Composable
private fun InvoiceListScreen(workspace: Workspace, nav: NavHostController, viewModel: OfficeFlowViewModel) {
    val state by viewModel.invoices.collectAsState()
    LaunchedEffect(workspace.workspaceId) { viewModel.loadInvoices() }
    Column(Modifier.fillMaxSize().padding(horizontal = 16.dp)) {
        Text("Vystavené faktúry", style = MaterialTheme.typography.headlineSmall)
        Text("Profil: ${workspace.displayName}", style = MaterialTheme.typography.labelMedium)
        Spacer(Modifier.height(8.dp))
        if (state.loading && state.items.isEmpty()) LoadingScreen()
        else LazyColumn(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
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
private fun InvoiceCard(invoice: InvoiceSummary, open: () -> Unit) {
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
private fun InvoiceDetailScreen(
    workspace: Workspace,
    invoiceId: Long,
    nav: NavHostController,
    viewModel: OfficeFlowViewModel,
) {
    val detail by viewModel.detail.collectAsState()
    LaunchedEffect(invoiceId, workspace.workspaceId) { viewModel.loadInvoice(invoiceId) }
    when (val state = detail) {
        DetailState.Idle, DetailState.Loading -> LoadingScreen()
        is DetailState.Error -> MessageScreen(state.message)
        is DetailState.Ready -> InvoiceDetailContent(state.invoice) {
            nav.navigate("invoice/$invoiceId/pdf")
        }
    }
}

@Composable
private fun InvoiceDetailContent(invoice: InvoiceDetail, openPdf: () -> Unit) {
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp)) {
        Text("Faktúra ${invoice.invoiceNumber}", style = MaterialTheme.typography.headlineSmall)
        Text(invoice.customer?.name ?: "Odberateľ neuvedený")
        Spacer(Modifier.height(12.dp))
        LabelValue("Vystavenie", invoice.issueDate)
        LabelValue("Dodanie", invoice.deliveryDate)
        LabelValue("Splatnosť", invoice.dueDate)
        LabelValue("Stav", invoice.status)
        LabelValue("Suma", "${money(invoice.totalAmount)} ${invoice.currency}")
        Spacer(Modifier.height(18.dp))
        Text("Položky", fontWeight = FontWeight.SemiBold)
        invoice.items.forEach { item ->
            HorizontalDivider(Modifier.padding(vertical = 8.dp))
            Text(item.description, fontWeight = FontWeight.Medium)
            item.detail?.takeIf(String::isNotBlank)?.let { Text(it) }
            Text("${item.quantity} ${item.unit} × ${money(item.unitPrice)} = ${money(item.totalPrice)}")
        }
        Spacer(Modifier.height(20.dp))
        Button(onClick = openPdf, modifier = Modifier.fillMaxWidth()) { Text("Zobraziť PDF") }
    }
}

@Composable
private fun ContactsScreen(workspace: Workspace, viewModel: OfficeFlowViewModel) {
    val state by viewModel.contacts.collectAsState()
    LaunchedEffect(workspace.workspaceId) { viewModel.loadContacts() }
    Column(Modifier.fillMaxSize().padding(horizontal = 16.dp)) {
        Text("Kontakty", style = MaterialTheme.typography.headlineSmall)
        Text("Profil: ${workspace.displayName}", style = MaterialTheme.typography.labelMedium)
        Spacer(Modifier.height(8.dp))
        if (state.loading) LoadingScreen()
        else LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            items(state.items, key = Contact::id) { contact ->
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
            item {
                if (state.items.isEmpty() && state.error == null) Text("Žiadne kontakty.")
                state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            }
        }
    }
}

@Composable
private fun PdfScreen(invoiceId: Long, viewModel: OfficeFlowViewModel) {
    val file by viewModel.pdf.collectAsState()
    LaunchedEffect(invoiceId) { viewModel.loadPdf(invoiceId) }
    DisposableEffect(invoiceId) { onDispose(viewModel::releasePdf) }
    when (val state = file) {
        PdfUiState.Idle, PdfUiState.Loading -> LoadingScreen()
        is PdfUiState.Error -> MessageScreen(state.message)
        is PdfUiState.Ready -> PdfPage(state.file)
    }
}

@Composable
private fun PdfPage(file: File) {
    var pageIndex by remember(file) { mutableStateOf(0) }
    val rendered by produceState<RenderedPdfPage?>(initialValue = null, file, pageIndex) {
        value = withContext(Dispatchers.IO) {
            ParcelFileDescriptor.open(file, ParcelFileDescriptor.MODE_READ_ONLY).use { descriptor ->
                PdfRenderer(descriptor).use { renderer ->
                    if (renderer.pageCount < 1) return@use null
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
                        RenderedPdfPage(bitmap, boundedIndex, renderer.pageCount)
                    }
                }
            }
        }
    }
    DisposableEffect(rendered?.bitmap) {
        onDispose { rendered?.bitmap?.recycle() }
    }
    Column(Modifier.fillMaxSize().padding(8.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        val page = rendered
        if (page == null) {
            LoadingScreen()
        } else {
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
                TextButton(onClick = { pageIndex -= 1 }, enabled = page.index > 0) { Text("Predchádzajúca") }
                Text("${page.index + 1} / ${page.count}")
                TextButton(onClick = { pageIndex += 1 }, enabled = page.index + 1 < page.count) { Text("Ďalšia") }
            }
        }
    }
}

private data class RenderedPdfPage(val bitmap: Bitmap, val index: Int, val count: Int)

private const val MAX_PDF_RENDER_DIMENSION = 4096

@Composable
private fun LabelValue(label: String, value: String) {
    Row(Modifier.fillMaxWidth().padding(vertical = 3.dp), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(label)
        Text(value, fontWeight = FontWeight.Medium)
    }
}

@Composable
private fun ContactLine(label: String, value: String?) {
    value?.takeIf(String::isNotBlank)?.let { Text("$label: $it") }
}

@Composable
private fun MessageScreen(message: String, vararg actions: Pair<String, () -> Unit>) {
    Column(
        Modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(message)
        actions.forEach { (label, action) ->
            Spacer(Modifier.height(10.dp))
            OutlinedButton(onClick = action) { Text(label) }
        }
    }
}

private fun money(value: Double): String = "%.2f".format(java.util.Locale.US, value)
