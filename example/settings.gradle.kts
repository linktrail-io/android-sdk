pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
        // The LinkTrail SDK AAR is hosted in this repo under /m2. External apps point at the raw
        // GitHub URL instead (see the top-level README); this demo resolves it from the local copy.
        maven { url = uri("${rootDir}/../m2") }
    }
}

rootProject.name = "kickflip-demo"
include(":app")
