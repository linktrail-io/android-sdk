package io.linktrail.example

import java.util.Locale
import kotlin.math.roundToLong

/** A shop category shown in the chip bar on the home screen. */
data class Category(val id: String, val name: String)

/** A single product. Its "image" is a tinted tile + emoji, so the demo needs no asset files. */
data class Product(
    val id: String,
    val name: String,
    val categoryId: String,
    val price: Double,
    val emoji: String,
    /** ARGB tint (the iOS system colour of the same name). */
    val tint: Long,
    val blurb: String,
) {
    val priceText: String get() = money(price)

    companion object {
        /** Whole-dollar price label, e.g. `$180`. */
        fun money(value: Double): String = "$" + String.format(Locale.US, "%.0f", value)
    }
}

/**
 * The link's own description in its `customData` (`linkType` + `source`, e.g. `campaign` / `e2e`).
 * Shown only in debug builds, so the e2e flows can assert which link type delivered the install.
 */
data class LinkMeta(val linkType: String?, val source: String?) {
    companion object {
        /** `null` when the link carries neither key. */
        fun from(customData: Map<String, String>?): LinkMeta? {
            val type = customData?.get("linkType")?.takeIf { it.isNotBlank() }
            val source = customData?.get("source")?.takeIf { it.isNotBlank() }
            return if (type == null && source == null) null else LinkMeta(type, source)
        }
    }
}

/** A voucher carried in a deep link's `customData` (`voucher` + `discountPercent`). */
data class Voucher(val code: String, val percentOff: Int) {
    /** The discounted price, rounded to whole dollars. */
    fun discountedPrice(price: Double): Double = (price * (1 - percentOff / 100.0)).roundToLong().toDouble()

    fun savings(price: Double): Double = price - discountedPrice(price)
}

/** iOS system colours, so the tiles match the iOS example. */
private object Tint {
    const val RED = 0xFFFF3B30
    const val ORANGE = 0xFFFF9500
    const val BLUE = 0xFF007AFF
    const val TEAL = 0xFF30B0C7
    const val PURPLE = 0xFFAF52DE
    const val INDIGO = 0xFF5856D6
    const val PINK = 0xFFFF2D55
    const val GREEN = 0xFF34C759
}

/** The demo's static storefront data. Same ids, names and prices as the iOS example. */
object Catalog {
    val categories: List<Category> = listOf(
        Category("basketball", "Basketball"),
        Category("running", "Running"),
        Category("lifestyle", "Lifestyle"),
        Category("skate", "Skate"),
    )

    val products: List<Product> = listOf(
        Product("aj1", "Air Jordan 1", "basketball", 180.0, "👟", Tint.RED, "The icon that started it all — premium leather, timeless colorway."),
        Product("dunk", "Dunk Low", "basketball", 110.0, "🏀", Tint.ORANGE, "Court-born, street-approved. An everyday staple."),
        Product("uboost", "UltraBoost", "running", 190.0, "🏃", Tint.BLUE, "Responsive cushioning built for the long miles."),
        Product("pegasus", "Pegasus 40", "running", 140.0, "⚡️", Tint.TEAL, "The workhorse daily trainer, refined again."),
        Product("am90", "Air Max 90", "lifestyle", 130.0, "✨", Tint.PURPLE, "Visible Air and heritage lines you know by heart."),
        Product("boost350", "Boost 350", "lifestyle", 220.0, "🌙", Tint.INDIGO, "Knit upper, sock-like fit, all-day comfort."),
        Product("oldskool", "Old Skool", "skate", 70.0, "🛹", Tint.PINK, "The classic side-stripe skate shoe."),
        Product("sbzoom", "SB Zoom", "skate", 100.0, "🔥", Tint.GREEN, "Board feel with Zoom Air pop."),
    )

    fun product(id: String): Product? = products.firstOrNull { it.id == id }

    fun category(id: String): Category? = categories.firstOrNull { it.id == id }

    /** The category's display name, or the id capitalised (like Swift's `capitalized`) if unknown. */
    fun categoryName(id: String): String = category(id)?.name ?: capitalized(id)

    internal fun capitalized(value: String): String {
        val out = StringBuilder(value.length)
        var startOfWord = true
        for (ch in value) {
            if (ch.isLetterOrDigit()) {
                out.append(if (startOfWord) ch.titlecaseChar() else ch.lowercaseChar())
                startOfWord = false
            } else {
                out.append(ch)
                startOfWord = true
            }
        }
        return out.toString()
    }
}
