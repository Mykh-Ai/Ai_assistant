package sk.zevsflow.officeflow

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.compose.viewModel
import sk.zevsflow.officeflow.ui.OfficeFlowApp
import sk.zevsflow.officeflow.ui.OfficeFlowTheme
import sk.zevsflow.officeflow.ui.OfficeFlowViewModel

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val container = (application as OfficeFlowApplication).container
        setContent {
            OfficeFlowTheme {
                val model: OfficeFlowViewModel = viewModel(
                    factory = object : ViewModelProvider.Factory {
                        @Suppress("UNCHECKED_CAST")
                        override fun <T : ViewModel> create(modelClass: Class<T>): T =
                            OfficeFlowViewModel(container) as T
                    }
                )
                OfficeFlowApp(model)
            }
        }
    }
}
