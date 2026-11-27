pluginManagement {
    repositories {
        maven {
            url = uri("https://maven.aliyun.com/repository/google")
            content {
                includeGroupByRegex("com\\.android(\\..*)?")
                includeGroupByRegex("androidx(\\..*)?")
                includeGroup("com.google.testing.platform")
            }
        }
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        maven {
            url = uri("https://maven.aliyun.com/repository/google")
            content {
                includeGroupByRegex("com\\.android(\\..*)?")
                includeGroupByRegex("androidx(\\..*)?")
                includeGroup("com.google.testing.platform")
            }
        }
        google()
        mavenCentral()
    }
}
rootProject.name = "SahamYar"
include(":app")
