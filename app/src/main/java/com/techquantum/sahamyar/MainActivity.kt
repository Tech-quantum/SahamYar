package com.techquantum.sahamyar

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.platform.LocalLayoutDirection

private val Background = Color(0xFF17191D)
private val SurfaceDark = Color(0xFF252930)
private val Orange = Color(0xFFFF8A00)
private val TextPrimary = Color(0xFFF5F5F5)
private val TextSecondary = Color(0xFFA6ABB3)
private val Green = Color(0xFF16C784)
private val Red = Color(0xFFEA5455)

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            SahamYarTheme {
                CompositionLocalProvider(LocalLayoutDirection provides LayoutDirection.Rtl) {
                    DashboardScreen()
                }
            }
        }
    }
}

@Composable
private fun SahamYarTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = darkColorScheme(
            primary = Orange,
            background = Background,
            surface = SurfaceDark,
            onBackground = TextPrimary,
            onSurface = TextPrimary
        ),
        content = content
    )
}

@Composable
private fun DashboardScreen() {
    Scaffold(
        containerColor = Background,
        bottomBar = { BottomNavigationBar() }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .statusBarsPadding()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 18.dp, vertical = 16.dp)
        ) {
            Header()
            Spacer(Modifier.height(24.dp))
            MarketStatusCard()
            Spacer(Modifier.height(24.dp))
            SectionTitle("نمای کلی بازار", "اطلاعات پس از اتصال به سرویس")
            Spacer(Modifier.height(12.dp))
            MarketOverview()
            Spacer(Modifier.height(24.dp))
            SectionTitle("نمادهای منتخب", "مشاهده دیده‌بان")
            Spacer(Modifier.height(12.dp))
            EmptyStateCard(
                "هنوز نمادی انتخاب نشده است",
                "نمادهای مورد علاقه‌ات را به دیده‌بان اضافه کن."
            )
            Spacer(Modifier.height(24.dp))
            SectionTitle("دسترسی سریع", null)
            Spacer(Modifier.height(12.dp))
            QuickAccessCard("جستجوی نماد", "جستجو در شرکت‌های بورس و فرابورس")
            QuickAccessCard("دیده‌بان من", "پیگیری نمادها و هشدارهای قیمتی")
            QuickAccessCard("سبد سرمایه‌گذاری", "مدیریت دارایی و محاسبه سود و زیان")
            QuickAccessCard("تحلیل هوشمند", "بررسی تکنیکال و تحلیل روند نمادها")
            Spacer(Modifier.height(20.dp))
        }
    }
}

@Composable
private fun Header() {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Column {
            Text("سهام‌یار", color = Orange, fontSize = 27.sp, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(4.dp))
            Text("دستیار هوشمند بازار سرمایه", color = TextSecondary, fontSize = 13.sp)
        }
        Surface(
            shape = RoundedCornerShape(14.dp),
            color = SurfaceDark
        ) {
            Text("ش", modifier = Modifier.padding(horizontal = 15.dp, vertical = 10.dp),
                color = Orange, fontSize = 20.sp, fontWeight = FontWeight.Bold)
        }
    }
}

@Composable
private fun MarketStatusCard() {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(18.dp),
        colors = CardDefaults.cardColors(containerColor = SurfaceDark)
    ) {
        Column(Modifier.padding(18.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text("وضعیت بازار", color = TextPrimary, fontSize = 17.sp,
                    fontWeight = FontWeight.Bold)
                Surface(color = Orange.copy(alpha = 0.15f), shape = RoundedCornerShape(20.dp)) {
                    Text("داده زنده غیرفعال", color = Orange, fontSize = 10.sp,
                        modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp))
                }
            }
            Spacer(Modifier.height(18.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                MarketExchange("بورس")
                MarketExchange("فرابورس")
            }
            Spacer(Modifier.height(14.dp))
            Text(
                "برای نمایش وضعیت واقعی بازار، اتصال به سرویس داده لازم است.",
                color = TextSecondary, fontSize = 12.sp, lineHeight = 19.sp
            )
        }
    }
}

@Composable
private fun RowScope.MarketExchange(name: String) {
    Surface(
        modifier = Modifier.weight(1f),
        color = Background,
        shape = RoundedCornerShape(12.dp)
    ) {
        Column(Modifier.padding(13.dp)) {
            Text(name, color = TextSecondary, fontSize = 12.sp)
            Spacer(Modifier.height(7.dp))
            Text("بدون داده", color = TextPrimary, fontSize = 14.sp,
                fontWeight = FontWeight.SemiBold)
        }
    }
}

@Composable
private fun SectionTitle(title: String, subtitle: String?) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(title, color = TextPrimary, fontSize = 17.sp, fontWeight = FontWeight.Bold)
        if (subtitle != null) {
            Text(subtitle, color = TextSecondary, fontSize = 10.sp)
        }
    }
}

@Composable
private fun MarketOverview() {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(9.dp)
    ) {
        OverviewCard("شاخص کل", "—", "در انتظار داده", Orange, Modifier.weight(1f))
        OverviewCard("شاخص هم‌وزن", "—", "در انتظار داده", TextSecondary, Modifier.weight(1f))
        OverviewCard("ارزش معاملات", "—", "در انتظار داده", TextSecondary, Modifier.weight(1f))
    }
}

@Composable
private fun OverviewCard(
    title: String,
    value: String,
    caption: String,
    accent: Color,
    modifier: Modifier
) {
    Card(
        modifier = modifier,
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(containerColor = SurfaceDark)
    ) {
        Column(Modifier.padding(11.dp)) {
            Text(title, color = TextSecondary, fontSize = 10.sp, maxLines = 1)
            Spacer(Modifier.height(12.dp))
            Text(value, color = accent, fontSize = 19.sp, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(5.dp))
            Text(caption, color = TextSecondary, fontSize = 9.sp, maxLines = 1)
        }
    }
}

@Composable
private fun EmptyStateCard(title: String, description: String) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(15.dp),
        colors = CardDefaults.cardColors(containerColor = SurfaceDark)
    ) {
        Column(
            modifier = Modifier.fillMaxWidth().padding(20.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text("☆", color = Orange, fontSize = 28.sp)
            Spacer(Modifier.height(8.dp))
            Text(title, color = TextPrimary, fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.height(5.dp))
            Text(description, color = TextSecondary, fontSize = 12.sp)
        }
    }
}

@Composable
private fun QuickAccessCard(title: String, description: String) {
    Card(
        modifier = Modifier.fillMaxWidth().padding(bottom = 9.dp),
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(containerColor = SurfaceDark)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(15.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(Modifier.weight(1f)) {
                Text(title, color = TextPrimary, fontWeight = FontWeight.SemiBold)
                Spacer(Modifier.height(4.dp))
                Text(description, color = TextSecondary, fontSize = 12.sp)
            }
            Text("‹", color = Orange, fontSize = 25.sp)
        }
    }
}

@Composable
private fun BottomNavigationBar() {
    NavigationBar(containerColor = SurfaceDark, contentColor = Orange) {
        val items = listOf("خانه", "بازار", "دیده‌بان", "سبد", "بیشتر")
        val symbols = listOf("⌂", "▥", "☆", "▣", "⋯")
        items.forEachIndexed { index, label ->
            NavigationBarItem(
                selected = index == 0,
                onClick = { },
                icon = { Text(symbols[index], fontSize = 20.sp) },
                label = { Text(label, fontSize = 10.sp) },
                alwaysShowLabel = true,
                colors = NavigationBarItemDefaults.colors(
                    selectedIconColor = Orange,
                    selectedTextColor = Orange,
                    indicatorColor = Orange.copy(alpha = 0.14f),
                    unselectedIconColor = TextSecondary,
                    unselectedTextColor = TextSecondary
                )
            )
        }
    }
}
