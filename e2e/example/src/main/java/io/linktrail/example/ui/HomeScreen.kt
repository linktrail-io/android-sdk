package io.linktrail.example.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.GridItemSpan
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.linktrail.example.Catalog
import io.linktrail.example.Category
import io.linktrail.example.Product
import io.linktrail.example.Store
import io.linktrail.example.ui.theme.KickFlipColors

/** The storefront: a category bar on top and a grid of products. Mirrors `HomeView` on iOS. */
@Composable
fun HomeScreen(store: Store) {
    LazyVerticalGrid(
        columns = GridCells.Fixed(2),
        modifier = Modifier.fillMaxSize().testTag("home"),
        contentPadding = PaddingValues(start = 16.dp, end = 16.dp, bottom = 24.dp),
        horizontalArrangement = Arrangement.spacedBy(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        item(span = { GridItemSpan(maxLineSpan) }) {
            CategoryBar(store.selectedCategory, store::selectCategory)
        }
        items(store.visibleProducts, key = { it.id }) { product ->
            ProductCard(product, onClick = { store.open(product) })
        }
    }
}

/** Horizontal category chips (including "All"). */
@Composable
private fun CategoryBar(selected: Category?, onSelect: (Category?) -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .horizontalScroll(rememberScrollState())
            .padding(top = 8.dp, bottom = 4.dp),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Chip("All", "category-all", selected == null) { onSelect(null) }
        Catalog.categories.forEach { category ->
            Chip(category.name, "category-${category.id}", selected == category) { onSelect(category) }
        }
    }
}

@Composable
private fun Chip(title: String, tag: String, isSelected: Boolean, onClick: () -> Unit) {
    Text(
        title,
        fontSize = 15.sp,
        fontWeight = FontWeight.SemiBold,
        color = if (isSelected) KickFlipColors.SystemBackground else KickFlipColors.Label,
        modifier = Modifier
            .clip(CircleShape)
            .background(if (isSelected) KickFlipColors.Label else KickFlipColors.SystemBackground)
            .clickable(onClick = onClick)
            .padding(horizontal = 16.dp, vertical = 8.dp)
            .testTag(tag),
    )
}

/** A product tile in the grid. */
@Composable
private fun ProductCard(product: Product, onClick: () -> Unit) {
    val shape = RoundedCornerShape(16.dp)
    Column(
        Modifier
            .clip(shape)
            .background(KickFlipColors.SystemBackground)
            .border(1.dp, KickFlipColors.Separator.copy(alpha = 0.5f), shape)
            .clickable(onClick = onClick)
            .testTag("product-card-${product.id}"),
    ) {
        Box(
            Modifier
                .fillMaxWidth()
                .height(130.dp)
                .background(Color(product.tint).copy(alpha = 0.18f)),
            contentAlignment = Alignment.Center,
        ) {
            Text(product.emoji, fontSize = 56.sp)
        }
        Column(Modifier.fillMaxWidth().padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(product.name, fontSize = 17.sp, fontWeight = FontWeight.SemiBold, maxLines = 1, overflow = TextOverflow.Ellipsis)
            Text(Catalog.categoryName(product.categoryId), fontSize = 12.sp, color = KickFlipColors.SecondaryLabel)
            Text(product.priceText, fontSize = 15.sp, fontWeight = FontWeight.SemiBold, modifier = Modifier.padding(top = 2.dp))
        }
    }
}
