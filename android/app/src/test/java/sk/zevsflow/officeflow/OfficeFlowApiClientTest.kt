package sk.zevsflow.officeflow

import java.io.File
import kotlinx.coroutines.test.runTest
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import sk.zevsflow.officeflow.data.ApiResult
import sk.zevsflow.officeflow.network.OfficeFlowApiClient

class OfficeFlowApiClientTest {
    @get:Rule val temporary = TemporaryFolder()
    private lateinit var server: MockWebServer
    private lateinit var api: OfficeFlowApiClient

    @Before fun startServer() {
        server = MockWebServer()
        server.start()
        api = OfficeFlowApiClient(server.url("/").toString())
    }

    @After fun stopServer() = server.shutdown()

    @Test fun enrollmentUsesOnlySecretBodyAndNeverAuthorizationClaim() = runTest {
        server.enqueue(sessionResponse())

        val result = api.exchangeEnrollment("ofenr_sensitive", "OfficeFlow Android")

        assertTrue(result is ApiResult.Success)
        val request = server.takeRequest()
        assertEquals("POST", request.method)
        assertEquals("/v1/enrollment/exchange", request.path)
        assertEquals(null, request.getHeader("Authorization"))
        val body = request.body.readUtf8()
        assertTrue(body.contains("ofenr_sensitive"))
        assertFalse(body.contains("principal_id"))
        assertFalse(body.contains("telegram_id"))
    }

    @Test fun invalidAndConsumedEnrollmentRemainBoundedFailures() = runTest {
        server.enqueue(errorResponse(401, "invalid_enrollment"))
        server.enqueue(errorResponse(401, "invalid_enrollment"))

        val invalid = api.exchangeEnrollment("ofenr_invalid", null)
        val replay = api.exchangeEnrollment("ofenr_consumed", null)

        assertEquals(ApiResult.HttpFailure(401, "invalid_enrollment"), invalid)
        assertEquals(ApiResult.HttpFailure(401, "invalid_enrollment"), replay)
    }

    @Test fun protectedReadsUseBearerAndExplicitWorkspaceScope() = runTest {
        server.enqueue(jsonResponse("""{"workspaces":[]}"""))
        server.enqueue(jsonResponse(invoiceListJson()))
        server.enqueue(jsonResponse(invoiceDetailJson()))
        server.enqueue(jsonResponse("""{"workspace_id":"ws-a","contacts":[]}"""))

        assertTrue(api.getWorkspaces("access-secret") is ApiResult.Success)
        assertTrue(api.getInvoices("access-secret", "ws-a", 50, 0) is ApiResult.Success)
        assertTrue(api.getInvoice("access-secret", "ws-a", 7) is ApiResult.Success)
        assertTrue(api.getContacts("access-secret", "ws-a") is ApiResult.Success)

        val paths = List(4) {
            server.takeRequest().also { request ->
                assertEquals("Bearer access-secret", request.getHeader("Authorization"))
                assertEquals("no-store", request.getHeader("Cache-Control"))
            }.path
        }
        assertEquals(
            listOf(
                "/v1/workspaces",
                "/v1/invoices?workspace_id=ws-a&limit=50&offset=0",
                "/v1/invoices/7?workspace_id=ws-a",
                "/v1/contacts?workspace_id=ws-a",
            ),
            paths,
        )
    }

    @Test fun productionShapedInvoiceDetailAcceptsNullableLegacyFields() = runTest {
        server.enqueue(jsonResponse(invoiceDetailJson(unit = null, customer = false)))

        val result = api.getInvoice("access-secret", "ws-a", 7)

        assertTrue(result is ApiResult.Success)
        val invoice = (result as ApiResult.Success).value.invoice
        assertNull(invoice.customer)
        assertEquals(1, invoice.items.size)
        assertNull(invoice.items.single().unit)
        assertEquals("August", invoice.items.single().detail)
        assertEquals("/v1/invoices/7?workspace_id=ws-a", server.takeRequest().path)
    }

    @Test fun invoiceDetailRetryKeepsTheSameExplicitWorkspaceScope() = runTest {
        server.enqueue(errorResponse(404, "not_found"))
        server.enqueue(jsonResponse(invoiceDetailJson()))

        assertEquals(
            ApiResult.HttpFailure(404, "not_found"),
            api.getInvoice("access-secret", "ws-a", 7),
        )
        assertTrue(api.getInvoice("access-secret", "ws-a", 7) is ApiResult.Success)

        assertEquals("/v1/invoices/7?workspace_id=ws-a", server.takeRequest().path)
        assertEquals("/v1/invoices/7?workspace_id=ws-a", server.takeRequest().path)
    }

    @Test fun pdfRequiresCorrectTypeSignatureAndPrivateCallerTarget() = runTest {
        server.enqueue(
            MockResponse().setResponseCode(200)
                .setHeader("Content-Type", "application/pdf")
                .setBody("%PDF-1.4\nfixture\n%%EOF\n")
        )
        val target = File(temporary.newFolder("private-cache"), "invoice.pdf")

        val result = api.downloadInvoicePdf("access", "ws-a", 7, target)

        assertEquals(ApiResult.Success(target), result)
        assertEquals("%PDF-", target.readBytes().copyOfRange(0, 5).decodeToString())
        val request = server.takeRequest()
        assertEquals("/v1/invoices/7/pdf?workspace_id=ws-a", request.path)
        assertEquals("Bearer access", request.getHeader("Authorization"))
    }

    @Test fun pdfRejectsMissingWrongTypeBadSignatureAndDeclaredOversize() = runTest {
        server.enqueue(errorResponse(404, "not_found"))
        server.enqueue(MockResponse().setHeader("Content-Type", "text/plain").setBody("not pdf"))
        server.enqueue(MockResponse().setHeader("Content-Type", "application/pdf").setBody("not pdf"))
        server.enqueue(
            MockResponse().setHeader("Content-Type", "application/pdf")
                .setBody("%PDF-")
                .setHeader("Content-Length", OfficeFlowApiClient.MAX_PDF_BYTES + 1)
        )

        val parent = temporary.newFolder("pdf-failures")
        assertEquals(
            ApiResult.HttpFailure(404, "not_found"),
            api.downloadInvoicePdf("a", "ws-a", 1, File(parent, "missing.pdf")),
        )
        assertEquals(
            ApiResult.ProtocolFailure("pdf_content_type_invalid"),
            api.downloadInvoicePdf("a", "ws-a", 2, File(parent, "wrong.pdf")),
        )
        assertEquals(
            ApiResult.ProtocolFailure("pdf_signature_invalid"),
            api.downloadInvoicePdf("a", "ws-a", 3, File(parent, "bad.pdf")),
        )
        assertEquals(
            ApiResult.ProtocolFailure("pdf_too_large"),
            api.downloadInvoicePdf("a", "ws-a", 4, File(parent, "large.pdf")),
        )
        assertTrue(parent.listFiles().isNullOrEmpty())
    }

    @Test fun revokeIsOnlyMutationCallAndContainsNoBody() = runTest {
        server.enqueue(MockResponse().setResponseCode(204))

        assertEquals(ApiResult.Success(Unit), api.revoke("access-secret"))

        val request = server.takeRequest()
        assertEquals("DELETE", request.method)
        assertEquals("/v1/session", request.path)
        assertEquals(0L, request.bodySize)
    }

    private fun sessionResponse() = jsonResponse(
        """{"session":{"access_token":"ofacc_new","refresh_token":"ofref_new","access_expires_at":"2026-08-20T00:15:00+00:00","refresh_expires_at":"2026-09-20T00:00:00+00:00","device_label":"Pixel"}}"""
    )

    private fun invoiceListJson() =
        """{"workspace_id":"ws-a","invoices":[{"id":7,"invoice_number":"20260007","issue_date":"2026-08-01","delivery_date":"2026-08-01","due_date":"2026-08-15","due_days":14,"total_amount":100.0,"currency":"EUR","status":"created","customer":{"id":2,"name":"Customer"}}],"limit":50,"offset":0}"""

    private fun invoiceDetailJson(unit: String? = "hour", customer: Boolean = true): String {
        val customerJson = if (customer) "{\"id\":2,\"name\":\"Customer\"}" else "null"
        val unitJson = unit?.let { "\"$it\"" } ?: "null"
        return """{"workspace_id":"ws-a","invoice":{"id":7,"invoice_number":"20260007","issue_date":"2026-08-01","delivery_date":"2026-08-01","due_date":"2026-08-15","due_days":14,"total_amount":100.0,"currency":"EUR","status":"created","customer":$customerJson,"items":[{"description":"Work","detail":"August","quantity":2.0,"unit":$unitJson,"unit_price":50.0,"total_price":100.0}]}}"""
    }

    private fun jsonResponse(body: String) = MockResponse()
        .setResponseCode(200)
        .setHeader("Content-Type", "application/json")
        .setBody(body)

    private fun errorResponse(status: Int, code: String) = MockResponse()
        .setResponseCode(status)
        .setHeader("Content-Type", "application/json")
        .setBody("""{"error":{"code":"$code"}}"""
        )
}
