package com.techquantum.sahamyar.data.local.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.Query
import androidx.room.Update
import com.techquantum.sahamyar.data.local.entity.PriceAlertEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface PriceAlertDao {
    @Query("SELECT * FROM price_alerts ORDER BY createdAtMillis DESC")
    fun observeAll(): Flow<List<PriceAlertEntity>>

    @Query("SELECT * FROM price_alerts WHERE isEnabled = 1 AND isTriggered = 0")
    suspend fun getPendingAlerts(): List<PriceAlertEntity>

    @Insert
    suspend fun insert(alert: PriceAlertEntity): Long

    @Update
    suspend fun update(alert: PriceAlertEntity): Int

    @Query("DELETE FROM price_alerts WHERE id = :id")
    suspend fun deleteById(id: Long): Int

    @Query("UPDATE price_alerts SET isTriggered = 0, isEnabled = 1, triggeredAtMillis = NULL, lastEvaluatedPriceRial = NULL WHERE id = :id")
    suspend fun resetAlert(id: Long): Int
}
