package com.techquantum.sahamyar.ui.stockdetail

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.Alignment
import androidx.compose.ui.graphics.Color
import com.techquantum.sahamyar.data.remote.model.StockHistoryItem
import java.util.Locale
import kotlin.math.max

private val ChartOrange = Color(0xFFFF8A00)
private val ChartMuted = Color(0xFFA6ABB3)
private val ChartGrid = Color(0xFF41464F)
private val ChartText = Color(0xFFF5F5F5)

@Composable
fun StockPriceChart(items: List<StockHistoryItem>) {
    var range by remember { mutableIntStateOf(30) }

    val points = remember(items, range) {
        items.filter {
            it.date != null && (it.closing_price ?: 0L) > 0L
        }.sortedBy { it.date }.takeLast(range)
    }

    var selectedIndex by remember(points) {
        mutableIntStateOf((points.size - 1).coerceAtLeast(0))
    }

    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = Color(0xFF252930))
    ) {
        Column(Modifier.padding(16.dp)) {
            Text("روند قیمت پایانی", color = ChartText, fontSize = 15.sp)
            Spacer(Modifier.height(10.dp))

            val selected = points.getOrNull(selectedIndex)
            Text(
                selected?.closing_price?.let {
                    "%,d ریال".format(Locale.US, it)
                } ?: "داده‌ای برای نمایش نیست",
                color = ChartOrange,
                fontSize = 21.sp
            )
            Text(
                selected?.date?.toString()?.let {
                    if (it.length == 8) "${it.substring(0, 4)}/${it.substring(4, 6)}/${it.substring(6, 8)}" else it
                } ?: "—",
                color = ChartMuted,
                fontSize = 11.sp
            )

            Spacer(Modifier.height(14.dp))

            Row(
                modifier = Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                listOf(7 to "۱ هفته", 30 to "۱ ماه", 90 to "۳ ماه", 180 to "۶ ماه", 365 to "۱ سال")
                    .forEach { (days, label) ->
                        FilterChip(
                            selected = range == days,
                            onClick = {
                                range = days
                                selectedIndex = 0
                            },
                            label = { Text(label, fontSize = 11.sp) },
                            colors = FilterChipDefaults.filterChipColors(
                                selectedContainerColor = ChartOrange,
                                selectedLabelColor = Color.Black
                            )
                        )
                    }
            }

            Spacer(Modifier.height(12.dp))

            if (points.size < 2) {
                Box(
                    Modifier.fillMaxWidth().height(170.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Text("برای رسم نمودار داده کافی نیست.", color = ChartMuted)
                }
            } else {
                Canvas(
                    modifier = Modifier.fillMaxWidth().height(190.dp)
                        .pointerInput(points) {
                            detectTapGestures { tap ->
                                val chartWidth = (size.width - 16.dp.toPx()).coerceAtLeast(1f)
                                val x = (tap.x - 8.dp.toPx()).coerceIn(0f, chartWidth)
                                selectedIndex = (
                                    x / chartWidth * (points.size - 1)
                                ).toInt().coerceIn(points.indices)
                            }
                        }
                ) {
                    val left = 8.dp.toPx()
                    val right = size.width - left
                    val top = 8.dp.toPx()
                    val bottom = size.height - 12.dp.toPx()
                    val values = points.map { it.closing_price!!.toDouble() }
                    val low = values.minOrNull() ?: 0.0
                    val high = values.maxOrNull() ?: 1.0
                    val spread = max(high - low, high * 0.02).toFloat()
                    val minValue = (low - spread * 0.08).toFloat()
                    val maxValue = (high + spread * 0.08).toFloat()

                    fun point(index: Int): Offset {
                        val x = left + (right - left) * index / (points.size - 1)
                        val ratio = (values[index].toFloat() - minValue) / (maxValue - minValue)
                        val y = bottom - ratio * (bottom - top)
                        return Offset(x, y)
                    }

                    for (i in 0..4) {
                        val y = top + (bottom - top) * i / 4
                        drawLine(ChartGrid, Offset(left, y), Offset(right, y), 1.dp.toPx())
                    }

                    val path = Path()
                    points.indices.forEach { index ->
                        val p = point(index)
                        if (index == 0) path.moveTo(p.x, p.y) else path.lineTo(p.x, p.y)
                    }

                    drawPath(
                        path = path,
                        color = ChartOrange,
                        style = Stroke(width = 3.dp.toPx(), cap = StrokeCap.Round)
                    )

                    val active = point(selectedIndex)
                    drawLine(
                        ChartMuted.copy(alpha = 0.6f),
                        Offset(active.x, top),
                        Offset(active.x, bottom),
                        1.dp.toPx()
                    )
                    drawCircle(ChartOrange, radius = 6.dp.toPx(), center = active)
                    drawCircle(Color.White, radius = 2.5.dp.toPx(), center = active)
                }
            }
        }
    }
}
