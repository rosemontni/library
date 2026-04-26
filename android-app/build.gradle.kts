import java.util.Locale

plugins {
    id("com.android.application") version "8.8.2" apply false
    id("org.jetbrains.kotlin.android") version "2.0.21" apply false
    id("org.jetbrains.kotlin.plugin.compose") version "2.0.21" apply false
}

val isWindows = System.getProperty("os.name").lowercase(Locale.US).contains("windows")
val localAppData = System.getenv("LOCALAPPDATA")

if (isWindows && !localAppData.isNullOrBlank()) {
    rootProject.layout.buildDirectory.set(file("$localAppData/LittleLibraryAtlasAndroidBuild/root"))
    subprojects {
        layout.buildDirectory.set(file("$localAppData/LittleLibraryAtlasAndroidBuild/${project.name}"))
    }
}
