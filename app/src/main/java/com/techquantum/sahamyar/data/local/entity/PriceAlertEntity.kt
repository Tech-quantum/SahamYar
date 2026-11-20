package com.techquantum.sahamyar.data.local.entity

import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "price_alerts",
    indices = [Index(value = ["insCode", "isEnabled"])]
)
data class PriceAlertEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val insCode: String,
    val symbol: String,
    val targetPriceRial: Long,
    // ABOVE or BELOW
    val condition: String,
    val isEnabled: Boolean = true,
    val isTriggered: Boolean = false,
    val createdAtMillis: Long = System.currentTimeMillis(),
    val triggeredAtMillis: Long? = null,
    val lastEvaluatedPriceRial: Long? = null
)
