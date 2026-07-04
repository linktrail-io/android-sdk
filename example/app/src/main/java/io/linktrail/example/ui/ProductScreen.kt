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
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.linktrail.example.Product
import io.linktrail.example.Voucher
import io.linktrail.model.LinkTrailLinkSource

@Composable
fun ProductScreen(product: Product, voucher: Voucher?, source: LinkTrailLinkSource?, onBack: () -> Unit) {
    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        TextButton(onClick = onBack) { Text("←  Back to store") }

        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(240.dp)
                .background(Color(product.colorArgb), RoundedCornerShape(20.dp)),
            contentAlignment = Alignment.Center,
        ) {
            Text(product.emoji, fontSize = 96.sp)
        }

        Text(product.name, fontSize = 22.sp, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onBackground)

        if (voucher != null) {
            VoucherBlock(product, voucher, source)
        } else {
            Text("$${product.priceUsd.toInt()}", fontSize = 20.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }

        Text(
            "Premium build, iconic silhouette, limited stock. Secure your pair before the drop sells out.",
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            fontSize = 14.sp,
        )

        Spacer(Modifier.height(4.dp))
        Button(onClick = {}, modifier = Modifier.fillMaxWidth()) {
            Text("Add to cart", fontWeight = FontWeight.SemiBold, modifier = Modifier.padding(vertical = 4.dp))
        }
    }
}

@Composable
private fun VoucherBlock(product: Product, voucher: Voucher, source: LinkTrailLinkSource?) {
    val discounted = voucher.discountedPrice(product.priceUsd)
    val savings = voucher.savings(product.priceUsd)

    Surface(shape = RoundedCornerShape(14.dp), color = Color(0xFF065F46), modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(
                "🏷️  ${voucher.code} — ${voucher.discountPercent}% off applied",
                color = Color.White,
                fontWeight = FontWeight.Bold,
                fontSize = 16.sp,
            )
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    "$${product.priceUsd.toInt()}",
                    color = Color(0xFFA7F3D0),
                    textDecoration = TextDecoration.LineThrough,
                    fontSize = 15.sp,
                )
                Spacer(Modifier.width(10.dp))
                Text("$${"%.2f".format(discounted)}", color = Color.White, fontWeight = FontWeight.Black, fontSize = 22.sp)
            }
            Text("You save $${"%.2f".format(savings)}", color = Color(0xFFA7F3D0), fontSize = 13.sp)
            if (source == LinkTrailLinkSource.DEFERRED) {
                Text("✨ Arrived via a deferred deep link", color = Color(0xFFD1FAE5), fontSize = 12.sp)
            }
        }
    }
}
