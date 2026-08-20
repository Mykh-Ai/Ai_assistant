package sk.zevsflow.officeflow.data

import android.content.Context

interface WorkspacePreferenceStore {
    fun remembered(): String?
    fun remember(workspaceId: String)
    fun clear()
}

class WorkspaceSelectionStore(context: Context) : WorkspacePreferenceStore {
    private val preferences = context.getSharedPreferences("officeflow_ui", Context.MODE_PRIVATE)

    override fun remembered(): String? = preferences.getString(KEY, null)

    override fun remember(workspaceId: String) {
        preferences.edit().putString(KEY, workspaceId).apply()
    }

    override fun clear() {
        preferences.edit().remove(KEY).apply()
    }

    companion object {
        private const val KEY = "selected_workspace_id"
    }
}

sealed interface WorkspaceChoice {
    data object Empty : WorkspaceChoice
    data class Selected(val workspace: Workspace) : WorkspaceChoice
    data class PickerRequired(val workspaces: List<Workspace>) : WorkspaceChoice
}

object WorkspaceSelectionPolicy {
    fun resolve(workspaces: List<Workspace>, rememberedId: String?): WorkspaceChoice {
        if (workspaces.isEmpty()) return WorkspaceChoice.Empty
        if (workspaces.size == 1) return WorkspaceChoice.Selected(workspaces.single())
        val remembered = workspaces.singleOrNull { it.workspaceId == rememberedId }
        return remembered?.let(WorkspaceChoice::Selected)
            ?: WorkspaceChoice.PickerRequired(workspaces)
    }
}
