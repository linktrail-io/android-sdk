package io.linktrail.example

/** Storefront categories shown in the home category bar. */
enum class Category(val label: String) {
    ALL("All"),
    BASKETBALL("Basketball"),
    RUNNING("Running"),
    LIFESTYLE("Lifestyle"),
    SKATE("Skate"),
}

/** A product. Its "image" is a colored tile + emoji so the demo needs no asset files. */
data class Product(
    val id: String,
    val name: String,
    val category: Category,
    val priceUsd: Double,
    val emoji: String,
    val colorArgb: Long,
)

object Catalog {
    val products = listOf(
        Product("aj1", "Air Jordan 1 Retro High OG", Category.BASKETBALL, 180.0, "👟", 0xFFB91C1C),
        Product("dunk-low", "Nike Dunk Low 'Panda'", Category.LIFESTYLE, 115.0, "👟", 0xFF111827),
        Product("pegasus-40", "Nike Pegasus 40", Category.RUNNING, 130.0, "👟", 0xFF2563EB),
        Product("nb-550", "New Balance 550", Category.LIFESTYLE, 120.0, "👟", 0xFF10B981),
        Product("blazer-mid", "Nike Blazer Mid '77", Category.SKATE, 105.0, "👟", 0xFFF59E0B),
        Product("ultraboost", "adidas Ultraboost Light", Category.RUNNING, 190.0, "👟", 0xFF7C3AED),
    )

    fun byId(id: String): Product? = products.firstOrNull { it.id == id }

    fun inCategory(category: Category): List<Product> =
        if (category == Category.ALL) products else products.filter { it.category == category }
}

/** A voucher that rode in on a deep link's `customData`. */
data class Voucher(val code: String, val discountPercent: Int) {
    fun discountedPrice(price: Double): Double = price * (1 - discountPercent / 100.0)
    fun savings(price: Double): Double = price - discountedPrice(price)
}
