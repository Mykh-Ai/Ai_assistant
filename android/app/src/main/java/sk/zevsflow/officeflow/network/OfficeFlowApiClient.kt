package sk.zevsflow.officeflow.network

import java.io.File
import java.io.IOException
import java.net.SocketTimeoutException
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.SerializationException
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import okhttp3.CacheControl
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.ResponseBody
import sk.zevsflow.officeflow.data.ApiResult
import sk.zevsflow.officeflow.data.ContactsEnvelope
import sk.zevsflow.officeflow.data.EnrollmentExchangeRequest
import sk.zevsflow.officeflow.data.ErrorEnvelope
import sk.zevsflow.officeflow.data.InvoiceDetailEnvelope
import sk.zevsflow.officeflow.data.InvoiceListEnvelope
import sk.zevsflow.officeflow.data.NetworkReason
import sk.zevsflow.officeflow.data.RefreshRequest
import sk.zevsflow.officeflow.data.SessionEnvelope
import sk.zevsflow.officeflow.data.SessionMetadataEnvelope
import sk.zevsflow.officeflow.data.WorkspacesEnvelope

class OfficeFlowApiClient(
    baseUrl: String,
    private val client: OkHttpClient = defaultHttpClient(),
    private val json: Json = Json { ignoreUnknownKeys = false; explicitNulls = false },
) {
    private val base = baseUrl.trimEnd('/').toHttpUrl()

    suspend fun exchangeEnrollment(
        enrollmentSecret: String,
        deviceLabel: String?,
    ): ApiResult<SessionEnvelope> = postJson(
        path = "/v1/enrollment/exchange",
        body = json.encodeToString(EnrollmentExchangeRequest(enrollmentSecret, deviceLabel)),
        serializer = SessionEnvelope.serializer(),
    )

    suspend fun refresh(refreshToken: String): ApiResult<SessionEnvelope> = postJson(
        path = "/v1/session/refresh",
        body = json.encodeToString(RefreshRequest(refreshToken)),
        serializer = SessionEnvelope.serializer(),
    )

    suspend fun revoke(accessToken: String): ApiResult<Unit> = executeUnit(
        Request.Builder()
            .url(url("/v1/session"))
            .delete()
            .authorized(accessToken)
            .build(),
        expectedStatus = 204,
    )

    suspend fun getSession(accessToken: String): ApiResult<SessionMetadataEnvelope> = getJson(
        "/v1/session",
        accessToken,
        SessionMetadataEnvelope.serializer(),
    )

    suspend fun getWorkspaces(accessToken: String): ApiResult<WorkspacesEnvelope> = getJson(
        "/v1/workspaces",
        accessToken,
        WorkspacesEnvelope.serializer(),
    )

    suspend fun getInvoices(
        accessToken: String,
        workspaceId: String,
        limit: Int,
        offset: Int,
    ): ApiResult<InvoiceListEnvelope> {
        require(limit in 1..100 && offset in 0..100_000)
        val url = url("/v1/invoices").newBuilder()
            .addQueryParameter("workspace_id", workspaceId)
            .addQueryParameter("limit", limit.toString())
            .addQueryParameter("offset", offset.toString())
            .build()
        return getJson(url, accessToken, InvoiceListEnvelope.serializer())
    }

    suspend fun getInvoice(
        accessToken: String,
        workspaceId: String,
        invoiceId: Long,
    ): ApiResult<InvoiceDetailEnvelope> {
        require(invoiceId > 0)
        val url = url("/v1/invoices/$invoiceId").newBuilder()
            .addQueryParameter("workspace_id", workspaceId)
            .build()
        return getJson(url, accessToken, InvoiceDetailEnvelope.serializer())
    }

    suspend fun getContacts(
        accessToken: String,
        workspaceId: String,
    ): ApiResult<ContactsEnvelope> {
        val url = url("/v1/contacts").newBuilder()
            .addQueryParameter("workspace_id", workspaceId)
            .build()
        return getJson(url, accessToken, ContactsEnvelope.serializer())
    }

    suspend fun downloadInvoicePdf(
        accessToken: String,
        workspaceId: String,
        invoiceId: Long,
        target: File,
    ): ApiResult<File> = withContext(Dispatchers.IO) {
        require(invoiceId > 0)
        val requestUrl = url("/v1/invoices/$invoiceId/pdf").newBuilder()
            .addQueryParameter("workspace_id", workspaceId)
            .build()
        val request = Request.Builder().url(requestUrl).get().authorized(accessToken).build()
        try {
            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) {
                    return@withContext failure(response.code, readBounded(response.body))
                }
                val body = response.body ?: return@withContext ApiResult.ProtocolFailure("pdf_body_missing")
                val contentType = body.contentType()
                if (contentType?.type != "application" || contentType.subtype != "pdf") {
                    return@withContext ApiResult.ProtocolFailure("pdf_content_type_invalid")
                }
                val declared = body.contentLength()
                if (declared > MAX_PDF_BYTES) {
                    return@withContext ApiResult.ProtocolFailure("pdf_too_large")
                }
                val parent = target.parentFile
                    ?: return@withContext ApiResult.ProtocolFailure("pdf_store_failed")
                if ((!parent.exists() && !parent.mkdirs()) || !parent.isDirectory) {
                    return@withContext ApiResult.ProtocolFailure("pdf_store_failed")
                }
                val temporary = File(parent, target.name + ".partial")
                try {
                    body.byteStream().use { input ->
                        temporary.outputStream().use { output ->
                            val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
                            var total = 0L
                            while (true) {
                                val read = input.read(buffer)
                                if (read < 0) break
                                total += read
                                if (total > MAX_PDF_BYTES) {
                                    throw PdfTooLargeException()
                                }
                                output.write(buffer, 0, read)
                            }
                        }
                    }
                    if (!temporary.inputStream().use { stream ->
                            val signature = ByteArray(5)
                            stream.read(signature) == 5 && signature.contentEquals("%PDF-".encodeToByteArray())
                        }
                    ) {
                        temporary.delete()
                        return@withContext ApiResult.ProtocolFailure("pdf_signature_invalid")
                    }
                    if (target.exists()) target.delete()
                    if (!temporary.renameTo(target)) {
                        temporary.delete()
                        return@withContext ApiResult.ProtocolFailure("pdf_store_failed")
                    }
                    ApiResult.Success(target)
                } catch (_: PdfTooLargeException) {
                    temporary.delete()
                    ApiResult.ProtocolFailure("pdf_too_large")
                }
            }
        } catch (_: SocketTimeoutException) {
            ApiResult.NetworkFailure(NetworkReason.TIMEOUT)
        } catch (_: IOException) {
            ApiResult.NetworkFailure(NetworkReason.UNAVAILABLE)
        }
    }

    private suspend fun <T> postJson(
        path: String,
        body: String,
        serializer: kotlinx.serialization.KSerializer<T>,
    ): ApiResult<T> {
        val request = Request.Builder()
            .url(url(path))
            .post(body.toRequestBody(JSON_MEDIA_TYPE))
            .header("Cache-Control", "no-store")
            .build()
        return executeJson(request, serializer)
    }

    private suspend fun <T> getJson(
        path: String,
        accessToken: String,
        serializer: kotlinx.serialization.KSerializer<T>,
    ): ApiResult<T> = getJson(url(path), accessToken, serializer)

    private suspend fun <T> getJson(
        requestUrl: okhttp3.HttpUrl,
        accessToken: String,
        serializer: kotlinx.serialization.KSerializer<T>,
    ): ApiResult<T> = executeJson(
        Request.Builder().url(requestUrl).get().authorized(accessToken).build(),
        serializer,
    )

    private suspend fun <T> executeJson(
        request: Request,
        serializer: kotlinx.serialization.KSerializer<T>,
    ): ApiResult<T> = withContext(Dispatchers.IO) {
        try {
            client.newCall(request).execute().use { response ->
                val body = readBounded(response.body)
                    ?: return@withContext ApiResult.ProtocolFailure("response_too_large")
                if (!response.isSuccessful) return@withContext failure(response.code, body)
                try {
                    ApiResult.Success(json.decodeFromString(serializer, body))
                } catch (_: SerializationException) {
                    ApiResult.ProtocolFailure("response_invalid")
                }
            }
        } catch (_: SocketTimeoutException) {
            ApiResult.NetworkFailure(NetworkReason.TIMEOUT)
        } catch (_: IOException) {
            ApiResult.NetworkFailure(NetworkReason.UNAVAILABLE)
        }
    }

    private suspend fun executeUnit(request: Request, expectedStatus: Int): ApiResult<Unit> =
        withContext(Dispatchers.IO) {
            try {
                client.newCall(request).execute().use { response ->
                    if (response.code == expectedStatus) ApiResult.Success(Unit)
                    else failure(response.code, readBounded(response.body))
                }
            } catch (_: SocketTimeoutException) {
                ApiResult.NetworkFailure(NetworkReason.TIMEOUT)
            } catch (_: IOException) {
                ApiResult.NetworkFailure(NetworkReason.UNAVAILABLE)
            }
        }

    private fun failure(status: Int, body: String?): ApiResult.HttpFailure {
        val code = try {
            body?.let { json.decodeFromString(ErrorEnvelope.serializer(), it).error.code }
        } catch (_: SerializationException) {
            null
        }
        return ApiResult.HttpFailure(status, code?.take(80) ?: "request_failed")
    }

    private fun readBounded(body: ResponseBody?): String? {
        if (body == null) return ""
        val source = body.source()
        if (source.request(MAX_JSON_BYTES.toLong() + 1L)) return null
        return source.readUtf8()
    }

    private fun url(path: String) = base.newBuilder()
        .encodedPath(path)
        .query(null)
        .build()

    private fun Request.Builder.authorized(accessToken: String): Request.Builder =
        header("Authorization", "Bearer $accessToken")
            .header("Cache-Control", "no-store")

    private class PdfTooLargeException : IOException()

    companion object {
        const val MAX_PDF_BYTES = 25L * 1024L * 1024L
        const val MAX_JSON_BYTES = 2 * 1024 * 1024
        private val JSON_MEDIA_TYPE = "application/json; charset=utf-8".toMediaType()

        fun defaultHttpClient(): OkHttpClient = OkHttpClient.Builder()
            .cache(null)
            .retryOnConnectionFailure(false)
            .connectTimeout(15, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .writeTimeout(15, TimeUnit.SECONDS)
            .build()
    }
}
