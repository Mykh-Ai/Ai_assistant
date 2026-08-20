package sk.zevsflow.officeflow

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Test
import sk.zevsflow.officeflow.data.SessionResult
import sk.zevsflow.officeflow.ui.DetailFailureKind
import sk.zevsflow.officeflow.ui.PdfFailureKind
import sk.zevsflow.officeflow.ui.detailFailureFor
import sk.zevsflow.officeflow.ui.pdfFailureFor
import sk.zevsflow.officeflow.ui.pdfRenderingFailure

class OfficeFlowDetailFailureTest {
    @Test fun detailFailuresRemainSpecificAndSafe() {
        assertEquals(
            DetailFailureKind.NOT_AVAILABLE,
            detailFailureFor(SessionResult.Failure("not_found")).kind,
        )
        assertEquals(
            DetailFailureKind.NETWORK,
            detailFailureFor(SessionResult.Failure("network_unavailable")).kind,
        )
        assertEquals(
            DetailFailureKind.PROTOCOL,
            detailFailureFor(SessionResult.Failure("response_invalid")).kind,
        )
        assertEquals(
            DetailFailureKind.UNEXPECTED,
            detailFailureFor(SessionResult.Failure("private_server_detail")).kind,
        )
    }

    @Test fun unexpectedServerTextIsNeverShownToTheUser() {
        val failure = detailFailureFor(SessionResult.Failure("private_server_detail"))

        assertFalse(failure.message.contains("private_server_detail"))
        assertEquals("Požiadavku sa nepodarilo dokončiť.", failure.message)
    }

    @Test fun pdfFailuresDistinguishAvailabilityNetworkProtocolAndRendering() {
        assertEquals(
            PdfFailureKind.NOT_AVAILABLE,
            pdfFailureFor(SessionResult.Failure("not_found")).kind,
        )
        assertEquals(
            PdfFailureKind.NETWORK,
            pdfFailureFor(SessionResult.Failure("network_unavailable")).kind,
        )
        assertEquals(
            PdfFailureKind.INVALID_RESPONSE,
            pdfFailureFor(SessionResult.Failure("pdf_signature_invalid")).kind,
        )
        assertEquals(PdfFailureKind.RENDERING, pdfRenderingFailure().kind)
    }

    @Test fun pdfFailuresNeverExposeUnexpectedServerDetails() {
        val failure = pdfFailureFor(SessionResult.Failure("private_server_path"))

        assertFalse(failure.message.contains("private_server_path"))
        assertEquals(PdfFailureKind.INVALID_RESPONSE, failure.kind)
    }
}
