package com.pulselink.cast.ui

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Matrix
import android.graphics.Paint
import android.util.AttributeSet
import android.view.GestureDetector
import android.view.MotionEvent
import android.view.ScaleGestureDetector
import android.view.View

class ZoomableStreamView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null
) : View(context, attrs) {

    private var currentBitmap: Bitmap? = null
    private val paint = Paint(Paint.FILTER_BITMAP_FLAG or Paint.ANTI_ALIAS_FLAG)
    private val drawMatrix = Matrix()

    var scaleFactor = 1.0f
        private set
    private var translateX = 0f
    private var translateY = 0f

    var trackpadMode: Boolean = false
    var onNormalizedTap: ((Float, Float, Boolean) -> Unit)? = null
    var onNormalizedMove: ((Float, Float) -> Unit)? = null

    private val scaleDetector = ScaleGestureDetector(context, object : ScaleGestureDetector.SimpleOnScaleGestureListener() {
        override fun onScale(detector: ScaleGestureDetector): Boolean {
            scaleFactor = (scaleFactor * detector.scaleFactor).coerceIn(1.0f, 4.5f)
            invalidate()
            return true
        }
    })

    private val gestureDetector = GestureDetector(context, object : GestureDetector.SimpleOnGestureListener() {
        override fun onSingleTapConfirmed(e: MotionEvent): Boolean {
            sendNormalizedPoint(e.x, e.y, isRightClick = false)
            return true
        }

        override fun onLongPress(e: MotionEvent) {
            sendNormalizedPoint(e.x, e.y, isRightClick = true)
        }

        override fun onScroll(e1: MotionEvent?, e2: MotionEvent, distanceX: Float, distanceY: Float): Boolean {
            if (scaleFactor > 1.05f && !trackpadMode) {
                translateX -= distanceX
                translateY -= distanceY
                invalidate()
            } else {
                val nx = (e2.x / width.coerceAtLeast(1)).coerceIn(0f, 1f)
                val ny = (e2.y / height.coerceAtLeast(1)).coerceIn(0f, 1f)
                onNormalizedMove?.invoke(nx, ny)
            }
            return true
        }
    })

    fun updateFrame(bitmap: Bitmap) {
        currentBitmap = bitmap
        postInvalidateOnAnimation()
    }

    fun getCurrentBitmap(): Bitmap? = currentBitmap

    fun resetZoom() {
        scaleFactor = 1.0f
        translateX = 0f
        translateY = 0f
        invalidate()
    }

    private fun sendNormalizedPoint(x: Float, y: Float, isRightClick: Boolean) {
        val nx = (x / width.coerceAtLeast(1)).coerceIn(0f, 1f)
        val ny = (y / height.coerceAtLeast(1)).coerceIn(0f, 1f)
        onNormalizedTap?.invoke(nx, ny, isRightClick)
    }

    override fun onTouchEvent(event: MotionEvent): Boolean {
        scaleDetector.onTouchEvent(event)
        gestureDetector.onTouchEvent(event)
        return true
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val bmp = currentBitmap ?: return
        canvas.save()
        canvas.translate(translateX, translateY)
        canvas.scale(scaleFactor, scaleFactor, width / 2f, height / 2f)

        val viewRatio = width.toFloat() / height.coerceAtLeast(1)
        val bmpRatio = bmp.width.toFloat() / bmp.height.coerceAtLeast(1)

        val drawW: Float
        val drawH: Float
        if (viewRatio > bmpRatio) {
            drawH = height.toFloat()
            drawW = drawH * bmpRatio
        } else {
            drawW = width.toFloat()
            drawH = drawW / bmpRatio
        }
        val left = (width - drawW) / 2f
        val top = (height - drawH) / 2f

        drawMatrix.reset()
        drawMatrix.postScale(drawW / bmp.width, drawH / bmp.height)
        drawMatrix.postTranslate(left, top)
        canvas.drawBitmap(bmp, drawMatrix, paint)
        canvas.restore()
    }
}
