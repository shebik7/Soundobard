plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "cz.soundobard"
    compileSdk = 35

    defaultConfig {
        applicationId = "cz.soundobard"
        minSdk = 26
        targetSdk = 35
        versionCode = (System.getenv("GITHUB_RUN_NUMBER") ?: "1").toInt()
        versionName = "1.0.${System.getenv("GITHUB_RUN_NUMBER") ?: "0"}"
    }

    // Fixed key committed to the repo so every build can be installed over the
    // previous one without losing imported sounds and settings.
    signingConfigs {
        create("soundboard") {
            storeFile = rootProject.file("keystore/soundboard.jks")
            storePassword = "soundboard"
            keyAlias = "soundboard"
            keyPassword = "soundboard"
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            signingConfig = signingConfigs.getByName("soundboard")
        }
        debug {
            signingConfig = signingConfigs.getByName("soundboard")
        }
    }

    // MP3 files dropped into the top-level `sounds/` folder ship inside the APK.
    sourceSets["main"].assets.srcDir(rootProject.file("sounds"))

    androidResources {
        noCompress += listOf("mp3", "ogg", "wav", "m4a", "aac", "flac")
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    buildFeatures {
        compose = true
    }
    lint {
        checkReleaseBuilds = false
    }
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2024.12.01")
    implementation(composeBom)
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.7")
    implementation("sh.calvin.reorderable:reorderable:2.4.3")
}
