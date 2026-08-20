package sk.zevsflow.officeflow

import org.junit.Assert.assertEquals
import org.junit.Assert.assertSame
import org.junit.Test
import sk.zevsflow.officeflow.data.Workspace
import sk.zevsflow.officeflow.data.WorkspaceChoice
import sk.zevsflow.officeflow.data.WorkspaceSelectionPolicy

class WorkspaceSelectionPolicyTest {
    private val first = Workspace("ws-a", "Firma A", "owner")
    private val second = Workspace("ws-b", "Firma B", "member")

    @Test fun zeroWorkspacesIsSafeEmptyState() {
        assertSame(WorkspaceChoice.Empty, WorkspaceSelectionPolicy.resolve(emptyList(), "ws-a"))
    }

    @Test fun exactlyOneWorkspaceIsSelectedWithoutRememberedState() {
        assertEquals(WorkspaceChoice.Selected(first), WorkspaceSelectionPolicy.resolve(listOf(first), null))
    }

    @Test fun multipleWorkspacesRequireExplicitSelection() {
        assertEquals(
            WorkspaceChoice.PickerRequired(listOf(first, second)),
            WorkspaceSelectionPolicy.resolve(listOf(first, second), null),
        )
    }

    @Test fun rememberedWorkspaceIsAcceptedOnlyAfterLatestListValidation() {
        assertEquals(
            WorkspaceChoice.Selected(second),
            WorkspaceSelectionPolicy.resolve(listOf(first, second), "ws-b"),
        )
        assertEquals(
            WorkspaceChoice.PickerRequired(listOf(first, second)),
            WorkspaceSelectionPolicy.resolve(listOf(first, second), "ws-stale"),
        )
    }
}
