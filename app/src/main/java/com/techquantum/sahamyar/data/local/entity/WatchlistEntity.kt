package com.techquantum.sahamyar.data.local.entity

import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "watchlist_items",
    indices = [Index(value = ["listId", "insCode"], unique = true)]
)
data class WatchlistEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val listId: String = "default",
    val insCode: String,
    val symbol: String,
    val companyName: String? = null,
    val market: String? = null,
    val addedAtMillis: Long = System.currentTimeMillis()
)
