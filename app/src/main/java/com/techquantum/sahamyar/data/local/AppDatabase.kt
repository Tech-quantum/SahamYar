package com.techquantum.sahamyar.data.local

import androidx.room.Database
import androidx.room.RoomDatabase
import com.techquantum.sahamyar.data.local.dao.PriceAlertDao
import com.techquantum.sahamyar.data.local.dao.WatchlistDao
import com.techquantum.sahamyar.data.local.entity.PriceAlertEntity
import com.techquantum.sahamyar.data.local.entity.WatchlistEntity

@Database(
    entities = [
        WatchlistEntity::class,
        PriceAlertEntity::class
    ],
    version = 1,
    exportSchema = true
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun watchlistDao(): WatchlistDao
    abstract fun priceAlertDao(): PriceAlertDao
}
