package sk.zevsflow.officeflow.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class SessionCredentials(
    @SerialName("access_token") val accessToken: String,
    @SerialName("refresh_token") val refreshToken: String,
    @SerialName("access_expires_at") val accessExpiresAt: String,
    @SerialName("refresh_expires_at") val refreshExpiresAt: String,
    @SerialName("device_label") val deviceLabel: String? = null,
    val refreshUncertain: Boolean = false,
)

@Serializable
data class SessionEnvelope(val session: SessionCredentials)

@Serializable
data class EnrollmentExchangeRequest(
    @SerialName("enrollment_secret") val enrollmentSecret: String,
    @SerialName("device_label") val deviceLabel: String? = null,
)

@Serializable
data class RefreshRequest(@SerialName("refresh_token") val refreshToken: String)

@Serializable
data class SessionMetadata(
    @SerialName("device_label") val deviceLabel: String? = null,
    @SerialName("created_at") val createdAt: String,
    @SerialName("last_seen_at") val lastSeenAt: String? = null,
    @SerialName("access_expires_at") val accessExpiresAt: String,
    @SerialName("refresh_expires_at") val refreshExpiresAt: String,
)

@Serializable
data class SessionMetadataEnvelope(val session: SessionMetadata)

@Serializable
data class Workspace(
    @SerialName("workspace_id") val workspaceId: String,
    @SerialName("display_name") val displayName: String,
    val role: String,
)

@Serializable
data class WorkspacesEnvelope(val workspaces: List<Workspace>)

@Serializable
data class InvoiceCustomer(val id: Long, val name: String)

@Serializable
data class InvoiceSummary(
    val id: Long,
    @SerialName("invoice_number") val invoiceNumber: String,
    @SerialName("issue_date") val issueDate: String,
    @SerialName("delivery_date") val deliveryDate: String,
    @SerialName("due_date") val dueDate: String,
    @SerialName("due_days") val dueDays: Int,
    @SerialName("total_amount") val totalAmount: Double,
    val currency: String,
    val status: String,
    val customer: InvoiceCustomer? = null,
)

@Serializable
data class InvoiceItem(
    val description: String,
    val detail: String? = null,
    val quantity: Double,
    val unit: String? = null,
    @SerialName("unit_price") val unitPrice: Double,
    @SerialName("total_price") val totalPrice: Double,
)

@Serializable
data class InvoiceDetail(
    val id: Long,
    @SerialName("invoice_number") val invoiceNumber: String,
    @SerialName("issue_date") val issueDate: String,
    @SerialName("delivery_date") val deliveryDate: String,
    @SerialName("due_date") val dueDate: String,
    @SerialName("due_days") val dueDays: Int,
    @SerialName("total_amount") val totalAmount: Double,
    val currency: String,
    val status: String,
    val customer: InvoiceCustomer? = null,
    val items: List<InvoiceItem>,
)

@Serializable
data class InvoiceListEnvelope(
    @SerialName("workspace_id") val workspaceId: String,
    val invoices: List<InvoiceSummary>,
    val limit: Int,
    val offset: Int,
)

@Serializable
data class InvoiceDetailEnvelope(
    @SerialName("workspace_id") val workspaceId: String,
    val invoice: InvoiceDetail,
)

@Serializable
data class Contact(
    val id: Long,
    val name: String,
    val ico: String? = null,
    val dic: String? = null,
    @SerialName("ic_dph") val icDph: String? = null,
    val address: String? = null,
    val email: String? = null,
    val iban: String? = null,
    @SerialName("contact_person") val contactPerson: String? = null,
)

@Serializable
data class ContactsEnvelope(
    @SerialName("workspace_id") val workspaceId: String,
    val contacts: List<Contact>,
)

@Serializable
data class ErrorBody(val code: String)

@Serializable
data class ErrorEnvelope(val error: ErrorBody)

sealed interface ApiResult<out T> {
    data class Success<T>(val value: T) : ApiResult<T>
    data class HttpFailure(val status: Int, val code: String) : ApiResult<Nothing>
    data class NetworkFailure(val reason: NetworkReason) : ApiResult<Nothing>
    data class ProtocolFailure(val reason: String) : ApiResult<Nothing>
}

enum class NetworkReason { TIMEOUT, UNAVAILABLE }

sealed interface SessionResult<out T> {
    data class Success<T>(val value: T) : SessionResult<T>
    data object EnrollmentRequired : SessionResult<Nothing>
    data object TemporarilyBlocked : SessionResult<Nothing>
    data object RefreshUncertain : SessionResult<Nothing>
    data class Failure(val message: String) : SessionResult<Nothing>
}
