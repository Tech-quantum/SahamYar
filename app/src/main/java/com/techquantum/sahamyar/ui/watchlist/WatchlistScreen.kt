package com.techquantum.sahamyar.ui.watchlist

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.techquantum.sahamyar.data.local.entity.WatchlistEntity

private val WatchlistBackground = Color(0xFF17191D)
private val WatchlistSurface = Color(0xFF252930)
private val WatchlistOrange = Color(0xFFFF8A00)
private val WatchlistText = Color(0xFFF5F5F5)
private val WatchlistMuted = Color(0xFFA6ABB3)
private val WatchlistRed = Color(0xFFEA5455)

@Composable
fun WatchlistScreen(
    modifier: Modifier = Modifier,
    onStockSelected: (String) -> Unit,
    watchlistViewModel: WatchlistViewModel = viewModel()
) {
    val stocks by watchlistViewModel.items.collectAsState()

    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(horizontal = 18.dp, vertical = 16.dp)
    ) {
        Text(
            text = "دیده‌بان من",
            color = WatchlistOrange,
            fontSize = 27.sp,
            fontWeight = FontWeight.Bold
        )
        Spacer(Modifier.height(6.dp))
        Text(
            text = "نمادهای منتخب برای پیگیری و تحلیل",
            color = WatchlistMuted,
            fontSize = 13.sp
        )
        Spacer(Modifier.height(22.dp))

        if (stocks.isEmpty()) {
            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(16.dp),
                colors = CardDefaults.cardColors(containerColor = WatchlistSurface)
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(24.dp),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Text("☆", color = WatchlistOrange, fontSize = 34.sp)
                    Spacer(Modifier.height(10.dp))
                    Text(
                        "دیده‌بان هنوز خالی است",
                        color = WatchlistText,
                        fontWeight = FontWeight.SemiBold
                    )
                    Spacer(Modifier.height(6.dp))
                    Text(
                        "از بخش بازار نمادهای موردنظرت را به دیده‌بان اضافه کن.",
                        color = WatchlistMuted,
                        fontSize = 12.sp
                    )
                }
            }
        } else {
            Text(
                text = "${stocks.size} نماد در دیده‌بان",
                color = WatchlistMuted,
                fontSize = 12.sp
            )
            Spacer(Modifier.height(12.dp))

            LazyColumn(
                verticalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                items(stocks, key = { it.id }) { stock ->
                    WatchlistItem(
                        stock = stock,
                        onClick = {
                            onStockSelected(stock.insCode)
                        },
                        onRemove = {
                            watchlistViewModel.removeStock(stock)
                        }
                    )
                }
            }
        }
    }
}

@Composable
private fun WatchlistItem(
    stock: WatchlistEntity,
    onClick: () -> Unit,
    onRemove: () -> Unit
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        shape = RoundedCornerShape(15.dp),
        colors = CardDefaults.cardColors(containerColor = WatchlistSurface)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(15.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    stock.symbol,
                    color = WatchlistOrange,
                    fontSize = 18.sp,
                    fontWeight = FontWeight.Bold
                )
                Spacer(Modifier.height(5.dp))
                Text(
                    stock.companyName ?: "نام شرکت ثبت نشده",
                    color = WatchlistText,
                    fontSize = 12.sp
                )
                Spacer(Modifier.height(4.dp))
                Text(
                    stock.market ?: "بازار نامشخص",
                    color = WatchlistMuted,
                    fontSize = 10.sp
                )
            }

            Text(
                text = "حذف",
                modifier = Modifier
                    .clickable(onClick = onRemove)
                    .padding(10.dp),
                color = WatchlistRed,
                fontSize = 12.sp
            )
        }
    }
}
