package io.linktrail.example

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import io.linktrail.model.LinkTrailDeepLink
import io.linktrail.model.LinkTrailLinkSource
import java.util.UUID

/**
 * Holds the demo's navigation + storefront state and translates a [LinkTrailDeepLink] (real or
 * simulated) into where the user lands. [route] is exactly the code a real app would put inside its
 * `onLink` handler. Mirrors `Store.swift` in the iOS example.
 */
class Store {

    /** Navigation stack for the home → product push. Empty == showing home. */
    var path: List<Product> by mutableStateOf(emptyList())
        private set

    /** Selected category chip on the home screen. `null` == "All". */
    var selectedCategory: Category? by mutableStateOf(null)
        private set

    /** Vouchers applied per product id (delivered via a deep link's meta). */
    private val appliedVouchers = mutableStateMapOf<String, Voucher>()

    /** The delivering link's `linkType` / `source` per product id (debug display only). */
    private val linkMetas = mutableStateMapOf<String, LinkMeta>()

    /** A transient "you arrived via a link" banner. */
    var banner: LandingBanner? by mutableStateOf(null)
        private set

    data class LandingBanner(
        val title: String,
        val subtitle: String,
        val source: LinkTrailLinkSource,
        val id: String = UUID.randomUUID().toString(),
    )

    val visibleProducts: List<Product>
        get() = selectedCategory?.let { category -> Catalog.products.filter { it.categoryId == category.id } }
            ?: Catalog.products

    fun voucher(product: Product): Voucher? = appliedVouchers[product.id]

    fun linkMeta(product: Product): LinkMeta? = linkMetas[product.id]

    fun selectCategory(category: Category?) {
        selectedCategory = category
    }

    fun open(product: Product) {
        path = path + product
    }

    /** Pops the top screen. Returns `false` when already on home. */
    fun pop(): Boolean {
        if (path.isEmpty()) return false
        path = path.dropLast(1)
        return true
    }

    /** Clears [banner] if it is still the one shown (a newer banner is left alone). */
    fun dismissBanner(id: String) {
        if (banner?.id == id) banner = null
    }

    // ── Deep-link routing ─────────────────────────────────────────────────────

    /**
     * Route a deep link into navigation state. The `path` decides the screen; `customData` carries
     * extras like a voucher. This is the whole integration surface.
     */
    fun route(link: LinkTrailDeepLink, source: LinkTrailLinkSource) {
        val destination = link.path

        // Scenario 3 & 4: a specific product (optionally with a voucher in the meta).
        if (destination.startsWith(PRODUCTS)) {
            val product = Catalog.product(destination.removePrefix(PRODUCTS)) ?: return landOnHome(source)
            selectedCategory = Catalog.category(product.categoryId)

            val code = link.customData?.get("voucher")
            if (code != null) {
                val percent = link.customData?.get("discountPercent")?.toIntOrNull() ?: 0
                appliedVouchers[product.id] = Voucher(code, percent)
            }
            // The latest link wins: a link without the keys clears an older link's meta.
            LinkMeta.from(link.customData)?.let { linkMetas[product.id] = it } ?: linkMetas.remove(product.id)
            path = listOf(product)
            banner = LandingBanner(
                title = title(source),
                subtitle = if (code != null) "Voucher $code applied to ${product.name}" else "Straight to ${product.name}",
                source = source,
            )
            return
        }

        // Scenario 2: home with a category pre-selected.
        if (destination.startsWith(CATEGORY)) {
            val categoryId = destination.removePrefix(CATEGORY)
            selectedCategory = Catalog.category(categoryId)
            path = emptyList()
            banner = LandingBanner(title(source), "${Catalog.categoryName(categoryId)} picks for you", source)
            return
        }

        // Scenario 1: just the storefront.
        landOnHome(source)
    }

    private fun landOnHome(source: LinkTrailLinkSource) {
        selectedCategory = null
        path = emptyList()
        banner = LandingBanner(title(source), "Browse the latest drops", source)
    }

    private fun title(source: LinkTrailLinkSource): String =
        if (source == LinkTrailLinkSource.DEFERRED) "Opened from your link" else "Welcome back"

    private companion object {
        const val PRODUCTS = "/products/"
        const val CATEGORY = "/category/"
    }
}
