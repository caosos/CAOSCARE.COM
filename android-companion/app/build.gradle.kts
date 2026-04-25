plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "care.caos.companion"
    compileSdk = 34
    defaultConfig {
        applicationId = "care.caos.companion"
        minSdk = 26
        targetSdk = 34
        versionCode = 1
        versionName = "0.1.0"
        // Native build is opt-in. Drop rtl_433 source under cpp/rtl_433/
        // and uncomment the externalNativeBuild block below to enable.
        // externalNativeBuild { cmake { cppFlags += "-std=c++17" } }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    buildFeatures { compose = true }
    composeOptions { kotlinCompilerExtensionVersion = "1.5.11" }
    packaging {
        resources.excludes += "/META-INF/{AL2.0,LGPL2.1}"
    }
    // externalNativeBuild { cmake { path = file("src/main/cpp/CMakeLists.txt") } }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.7.0")
    implementation("androidx.lifecycle:lifecycle-service:2.7.0")
    implementation("androidx.activity:activity-compose:1.9.0")
    val composeBom = platform("androidx.compose:compose-bom:2024.04.01")
    implementation(composeBom)
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    implementation("androidx.datastore:datastore-preferences:1.1.0")
    // ZXing for QR scanning
    implementation("com.journeyapps:zxing-android-embedded:4.3.0")
    // Networking — kotlin serialization + ktor
    implementation("io.ktor:ktor-client-android:2.3.10")
    implementation("io.ktor:ktor-client-content-negotiation:2.3.10")
    implementation("io.ktor:ktor-serialization-kotlinx-json:2.3.10")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.6.3")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.0")
}
