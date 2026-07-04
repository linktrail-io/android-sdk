package io.linktrail.example

import android.net.Uri
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import io.linktrail.model.LinkTrailDeepLink
import io.linktrail.model.LinkTrailLinkSource

/** The screen the store is showing. */
sealed interface Screen {
    data object Home : Screen
    data class ProductDetail(val product: Product, val voucher: Voucher?) : Screen
}

/**
 * The store's UI state and — crucially — the **single** method the whole SDK integration collapses
 * into: [route]. It reads `link.deepLinkPath` and `link.customData` and decides the screen. It's
 * wired once via `onLink`; the debug simulator fires the same [LinkTrailDeepLink] objects into it.
 */
class Store : ViewModel() {

    var screen by mutableStateOf<Screen>(Screen.Home)
        private set
    var selectedCategory by mutableStateOf(Category.ALL)
        private set
    var lastSource by mutableStateOf<LinkTrailLinkSource?>(null)
        private set

    fun selectCategory(category: Category) { selectedCategory = category }
    fun openProduct(product: Product) { screen = Screen.ProductDetail(product, null) }
    fun goHome() { screen = Screen.Home }

    /** The entire SDK surface the app touches: turn a deep link into a destination. */
    fun route(link: LinkTrailDeepLink, source: LinkTrailLinkSource) {
        lastSource = source
        val path = link.path
        when {
            path.startsWith("/products/") -> {
                val product = Catalog.byId(path.substringAfterLast('/')) ?: Catalog.products.first()
                val voucher = link.customData?.get("voucher")?.let { code ->
                    Voucher(code, link.customData?.get("discountPercent")?.toIntOrNull() ?: 0)
                }
                screen = Screen.ProductDetail(product, voucher)
            }

            path.startsWith("/category/") -> {
                val name = path.substringAfterLast('/')
                selectedCategory = Category.entries.firstOrNull { it.label.equals(name, ignoreCase = true) } ?: Category.ALL
                screen = Screen.Home
            }

            else -> {
                selectedCategory = Category.ALL
                screen = Screen.Home
            }
        }
    }

    /** Fire a debug scenario locally (no backend round-trip) — the demo's point. */
    fun simulate(scenario: SimScenario) = route(scenario.link, LinkTrailLinkSource.DEFERRED)

    /**
     * Offline convenience: route a raw incoming URI directly (used when the SDK isn't configured,
     * e.g. the `kickflip://products/aj1?voucher=…` adb test). With a configured SDK + backend the
     * link is instead resolved via `handleDeepLink` → `onLink`.
     */
    fun routeUri(uri: Uri) = route(uriToLink(uri), LinkTrailLinkSource.REENGAGEMENT)

    private fun uriToLink(uri: Uri): LinkTrailDeepLink {
        val isWeb = uri.scheme == "http" || uri.scheme == "https"
        val path = if (isWeb) uri.path ?: "/" else "/" + (uri.host ?: "") + (uri.path ?: "")
        val customData = uri.queryParameterNames.associateWith { uri.getQueryParameter(it) ?: "" }
        return LinkTrailDeepLink(
            url = uri.toString(),
            deepLinkPath = path,
            customData = customData.ifEmpty { null },
        )
    }
}

/** The four deferred scenarios from the spec, fired by the debug simulator panel. */
enum class SimScenario(val title: String, val subtitle: String, val link: LinkTrailDeepLink) {
    STORE(
        "Just the store",
        "deepLinkPath: \"/\" → Home",
        LinkTrailDeepLink(deepLinkPath = "/"),
    ),
    CATEGORY(
        "Category selected",
        "deepLinkPath: \"/category/running\" → Home, Running pre-selected",
        LinkTrailDeepLink(deepLinkPath = "/category/running"),
    ),
    PRODUCT(
        "A product",
        "deepLinkPath: \"/products/aj1\" → Air Jordan 1",
        LinkTrailDeepLink(deepLinkPath = "/products/aj1"),
    ),
    PRODUCT_VOUCHER(
        "Product + voucher",
        "\"/products/aj1\" + customData {voucher: SUMMER25, 25%}",
        LinkTrailDeepLink(
            deepLinkPath = "/products/aj1",
            customData = mapOf("voucher" to "SUMMER25", "discountPercent" to "25"),
        ),
    ),
}
