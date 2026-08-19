import java.net.URI

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
    id("org.jetbrains.kotlin.plugin.serialization")
}

val debugApiUrl = providers.gradleProperty("OFFICEFLOW_DEBUG_API_BASE_URL")
    .orElse("http://10.0.2.2:8081")
    .get()
    .trimEnd('/')
val releaseApiUrl = providers.gradleProperty("OFFICEFLOW_API_BASE_URL")
    .orNull
    ?.trim()
    ?.trimEnd('/')

fun quoted(value: String): String = "\"${value.replace("\\", "\\\\").replace("\"", "\\\"")}\""

fun validateDebugUrl(value: String) {
    val uri = URI(value)
    require(
        (uri.scheme == "http" && uri.host == "10.0.2.2") || uri.scheme == "https"
    ) { "Debug OfficeFlow URL must be HTTPS or the explicit 10.0.2.2 emulator endpoint." }
    require(uri.userInfo == null && uri.query == null && uri.fragment == null)
}

fun validateReleaseUrl(value: String?) {
    require(!value.isNullOrBlank()) {
        "OFFICEFLOW_API_BASE_URL is required for release builds."
    }
    val uri = URI(value)
    require(uri.scheme == "https" && !uri.host.isNullOrBlank()) {
        "Release OfficeFlow URL must use HTTPS."
    }
    require(uri.userInfo == null && uri.query == null && uri.fragment == null)
}

validateDebugUrl(debugApiUrl)

android {
    namespace = "sk.zevsflow.officeflow"
    compileSdk = 35

    defaultConfig {
        applicationId = "sk.zevsflow.officeflow"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "0.1.0-stage-b"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        vectorDrawables.useSupportLibrary = true
    }

    buildTypes {
        debug {
            applicationIdSuffix = ".debug"
            versionNameSuffix = "-debug"
            buildConfigField("String", "OFFICEFLOW_API_BASE_URL", quoted(debugApiUrl))
        }
        release {
            isMinifyEnabled = false
            buildConfigField(
                "String",
                "OFFICEFLOW_API_BASE_URL",
                quoted(releaseApiUrl ?: "https://missing.invalid"),
            )
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
        }
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }

    packaging {
        resources.excludes += "/META-INF/{AL2.0,LGPL2.1}"
    }
}

tasks.matching { it.name == "preReleaseBuild" }.configureEach {
    doFirst { validateReleaseUrl(releaseApiUrl) }
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2025.05.01")

    implementation("androidx.core:core-ktx:1.16.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.9.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.9.0")
    implementation("androidx.activity:activity-compose:1.10.1")
    implementation("androidx.navigation:navigation-compose:2.9.0")
    implementation(composeBom)
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.10.2")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.8.1")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")

    debugImplementation("androidx.compose.ui:ui-tooling")
    debugImplementation("androidx.compose.ui:ui-test-manifest")

    testImplementation("junit:junit:4.13.2")
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.10.2")
    testImplementation("com.squareup.okhttp3:mockwebserver:4.12.0")
    testImplementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.8.1")

    androidTestImplementation(composeBom)
    androidTestImplementation("androidx.test.ext:junit:1.2.1")
    androidTestImplementation("androidx.test:runner:1.6.2")
    androidTestImplementation("androidx.test:core-ktx:1.6.1")
    androidTestImplementation("androidx.compose.ui:ui-test-junit4")
}
