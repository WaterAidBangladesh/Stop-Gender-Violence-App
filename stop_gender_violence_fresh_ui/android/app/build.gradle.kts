import java.util.Properties
import java.io.File

plugins {
    id("com.android.application")
    id("kotlin-android")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
    id("com.google.gms.google-services")
}

android {
    namespace = "com.wateraidbd.shomotashurokkha"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }

    kotlinOptions {
        jvmTarget = JavaVersion.VERSION_11.toString()
    }

    defaultConfig {
        applicationId = "com.wateraidbd.shomotashurokkha"
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        versionCode = 5
        versionName = "1.1"
    }

    // Release signing is optional: if key.properties or the keystore is missing,
    // release builds fall back to debug signing instead of breaking every build.
    val keyPropertiesFile = rootProject.file("key.properties")
    val keyProperties = Properties()
    if (keyPropertiesFile.exists()) {
        keyPropertiesFile.inputStream().use { keyProperties.load(it) }
    }
    // Relative storeFile paths are resolved against the android/ directory.
    val releaseKeystore = keyProperties.getProperty("storeFile")?.let { rootProject.file(it) }
    val hasReleaseKeystore = releaseKeystore != null && releaseKeystore.exists()

    signingConfigs {
        if (hasReleaseKeystore) {
            create("release") {
                keyAlias = keyProperties.getProperty("keyAlias")
                keyPassword = keyProperties.getProperty("keyPassword")
                storeFile = releaseKeystore
                storePassword = keyProperties.getProperty("storePassword")
            }
        } else {
            logger.warn("Release keystore not found; release builds will use debug signing.")
        }
    }

    buildTypes {
        getByName("release") {
            signingConfig = signingConfigs.getByName(if (hasReleaseKeystore) "release" else "debug")
            isMinifyEnabled = false       // Disable code shrinking
            isShrinkResources = false     // Disable resource shrinking
        }
        getByName("debug") {
            signingConfig = signingConfigs.getByName("debug")
        }
    }
}

flutter {
    source = "../.."
}

dependencies {
    implementation(platform("com.google.firebase:firebase-bom:34.6.0"))
}
