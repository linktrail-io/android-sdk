package io.linktrail.example

import android.app.Application
import io.linktrail.example.sdk.AttributionCoordinator

/**
 * Owns the app-wide [Store] and [AttributionCoordinator], and configures the LinkTrail SDK once in
 * `onCreate` (like `KickFlipDemoApp` on iOS). Keeping the store at app level means a deferred link
 * that resolves before or between activities still lands in the one store the UI reads.
 */
class KickFlipApp : Application() {
    lateinit var store: Store
        private set
    lateinit var coordinator: AttributionCoordinator
        private set

    override fun onCreate() {
        super.onCreate()
        store = Store()
        coordinator = AttributionCoordinator(this, store)
        coordinator.configureSdk(this)
    }
}
