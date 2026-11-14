package io.linktrail.example.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.linktrail.example.BuildConfig
import io.linktrail.example.Catalog
import io.linktrail.example.LinkMeta
import io.linktrail.example.Product
import io.linktrail.example.Voucher
import io.linktrail.example.ui.theme.KickFlipColors

/**
 * A single product page. If a voucher was delivered for this product (via a deep link's meta), it
 * shows the voucher badge and the discounted price. Mirrors `ProductView` on iOS. Debug builds also
 * show the link's `linkType` / `source` meta (test tags `meta-linkType` / `meta-source`) for the e2e
 * link-type flows; release builds never do.
 */
@Composable
fun ProductScreen(product: Product, voucher: Voucher?, meta: LinkMeta? = null, showMeta: Boolean = BuildConfig.DEBUG) {
    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp)
            .testTag("product-${product.id}"),
        verticalArrangement = Arrangement.spacedBy(20.dp),
    ) {
        Box(
            Modifier
                .fillMaxWidth()
                .height(260.dp)
                .clip(RoundedCornerShape(24.dp))
                .background(Color(product.tint).copy(alpha = 0.18f)),
            contentAlignment = Alignment.Center,
        ) {
            Text(product.emoji, fontSize = 120.sp)
        }

        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(Catalog.categoryName(product.categoryId), fontSize = 15.sp, color = KickFlipColors.SecondaryLabel)
            Text(
                product.name,
                fontSize = 34.sp,
                lineHeight = 40.sp,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.testTag("product-name"),
            )
            Text(product.blurb, fontSize = 17.sp, color = KickFlipColors.SecondaryLabel)
        }

        if (showMeta && meta != null) LinkMetaRow(meta)

        PriceBlock(product, voucher)

        Button(
            onClick = { /* Add-to-bag is out of scope for the demo (same as iOS). */ },
            shape = RoundedCornerShape(14.dp),
            colors = ButtonDefaults.buttonColors(containerColor = Color(product.tint), contentColor = Color.White),
            modifier = Modifier.fillMaxWidth().height(56.dp),
        ) {
            Text("Add to Bag", fontSize = 17.sp, fontWeight = FontWeight.SemiBold)
        }
    }
}

/** Debug-only: the delivering link's meta. Each value is its own node, so Maestro can match it exactly. */
@Composable
private fun LinkMetaRow(meta: LinkMeta) {
    Row(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .background(KickFlipColors.SecondaryLabel.copy(alpha = 0.12f))
            .padding(horizontal = 12.dp, vertical = 8.dp)
            .testTag("link-meta"),
        horizontalArrangement = Arrangement.spacedBy(6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        val label = KickFlipColors.SecondaryLabel
        Text("linkType", fontSize = 13.sp, color = label)
        Text(meta.linkType ?: "-", fontSize = 13.sp, fontWeight = FontWeight.SemiBold, modifier = Modifier.testTag("meta-linkType"))
        Text("·  source", fontSize = 13.sp, color = label)
        Text(meta.source ?: "-", fontSize = 13.sp, fontWeight = FontWeight.SemiBold, modifier = Modifier.testTag("meta-source"))
    }
}

@Composable
private fun PriceBlock(product: Product, voucher: Voucher?) {
    if (voucher == null) {
        Text(product.priceText, fontSize = 28.sp, fontWeight = FontWeight.Bold, modifier = Modifier.testTag("price"))
        return
    }
    val green = KickFlipColors.Green
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Row(
            Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(12.dp))
                .background(green.copy(alpha = 0.15f))
                .padding(12.dp)
                .testTag("voucher-badge"),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text("🏷", fontSize = 15.sp)
            Text(
                "Voucher ${voucher.code} applied · ${voucher.percentOff}% off",
                fontSize = 15.sp,
                fontWeight = FontWeight.SemiBold,
                color = green,
            )
        }
        Row(verticalAlignment = Alignment.Bottom, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            Text(
                Product.money(voucher.discountedPrice(product.price)),
                fontSize = 28.sp,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.testTag("price"),
            )
            Text(
                product.priceText,
                fontSize = 20.sp,
                color = KickFlipColors.SecondaryLabel,
                textDecoration = TextDecoration.LineThrough,
                modifier = Modifier.padding(bottom = 2.dp),
            )
            Spacer(Modifier.weight(1f))
            Text(
                "Save ${Product.money(voucher.savings(product.price))}",
                fontSize = 12.sp,
                fontWeight = FontWeight.SemiBold,
                color = green,
                modifier = Modifier
                    .clip(CircleShape)
                    .background(green.copy(alpha = 0.15f))
                    .padding(horizontal = 8.dp, vertical = 4.dp)
                    .align(Alignment.CenterVertically),
            )
        }
    }
}
