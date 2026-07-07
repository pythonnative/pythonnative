package com.pythonnative.android_template;

import android.content.Context;
import android.util.TypedValue;
import android.view.ViewGroup;
import android.widget.FrameLayout;

import androidx.annotation.NonNull;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

/**
 * RecyclerView-backed virtualized list used by PythonNative's Android bridge.
 *
 * <p>Chaquopy can proxy Java interfaces from Python, but it can't subclass Java
 * abstract classes such as RecyclerView.Adapter or RecyclerView.ViewHolder. This
 * helper owns those abstract-class implementations in Java and delegates row
 * content back to Python through the small Delegate interface below.</p>
 *
 * <p>Rows may have per-position heights (section lists interleave headers and
 * items); the delegate reports each row's height in dp. Scroll changes are
 * forwarded to the delegate in dp so the Python side can drive on_scroll,
 * on_end_reached, and viewability callbacks with one code path per platform.</p>
 */
public class PNVirtualListView extends RecyclerView {
    public interface Delegate {
        int getCount();

        float getRowHeightDp(int position);

        void mountRow(int position, FrameLayout container, float widthDp, float heightDp);

        void onRowPress(int position);

        void onRowRecycled(FrameLayout container);

        void onScrolled(float offsetDp, float extentDp, float rangeDp);
    }

    private final float density;
    private final RowAdapter rowAdapter;
    private Delegate delegate;

    public PNVirtualListView(@NonNull Context context, @NonNull Delegate delegate) {
        super(context);
        this.delegate = delegate;
        this.density = context.getResources().getDisplayMetrics().density;
        setLayoutManager(new LinearLayoutManager(context));
        rowAdapter = new RowAdapter();
        setAdapter(rowAdapter);
        addOnScrollListener(new OnScrollListener() {
            @Override
            public void onScrolled(@NonNull RecyclerView rv, int dx, int dy) {
                PNVirtualListView.this.delegate.onScrolled(
                    rv.computeVerticalScrollOffset() / PNVirtualListView.this.density,
                    rv.computeVerticalScrollExtent() / PNVirtualListView.this.density,
                    rv.computeVerticalScrollRange() / PNVirtualListView.this.density
                );
            }
        });
    }

    public void setDelegate(@NonNull Delegate delegate) {
        this.delegate = delegate;
        rowAdapter.notifyDataSetChanged();
    }

    public void notifyDataChanged() {
        rowAdapter.notifyDataSetChanged();
    }

    public void scrollToOffsetDp(float offsetDp, boolean animated) {
        int targetPx = Math.round(offsetDp * density);
        int currentPx = computeVerticalScrollOffset();
        if (animated) {
            smoothScrollBy(0, targetPx - currentPx);
        } else {
            scrollBy(0, targetPx - currentPx);
        }
    }

    public void scrollToIndex(int position, boolean animated) {
        int clamped = Math.max(0, Math.min(position, Math.max(0, delegate.getCount() - 1)));
        if (animated) {
            smoothScrollToPosition(clamped);
        } else {
            scrollToPosition(clamped);
        }
    }

    private int rowHeightPx(int position) {
        return Math.max(
            1,
            Math.round(TypedValue.applyDimension(
                TypedValue.COMPLEX_UNIT_DIP,
                delegate.getRowHeightDp(position),
                getResources().getDisplayMetrics()
            ))
        );
    }

    private float currentWidthDp(FrameLayout container) {
        int widthPx = container.getWidth();
        if (widthPx <= 0) {
            widthPx = getWidth();
        }
        if (widthPx <= 0) {
            widthPx = getResources().getDisplayMetrics().widthPixels;
        }
        return widthPx / density;
    }

    private class RowHolder extends RecyclerView.ViewHolder {
        final FrameLayout container;

        RowHolder(@NonNull FrameLayout container) {
            super(container);
            this.container = container;
        }
    }

    private class RowAdapter extends RecyclerView.Adapter<RowHolder> {
        @Override
        public int getItemCount() {
            return delegate.getCount();
        }

        @NonNull
        @Override
        public RowHolder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
            FrameLayout container = new FrameLayout(parent.getContext());
            container.setLayoutParams(
                new RecyclerView.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    ViewGroup.LayoutParams.WRAP_CONTENT
                )
            );
            return new RowHolder(container);
        }

        @Override
        public void onBindViewHolder(@NonNull RowHolder holder, int position) {
            RecyclerView.LayoutParams params = (RecyclerView.LayoutParams) holder.container.getLayoutParams();
            int heightPx = rowHeightPx(position);
            if (params.height != heightPx) {
                params.height = heightPx;
                holder.container.setLayoutParams(params);
            }
            holder.container.removeAllViews();
            holder.container.setOnClickListener(v -> {
                int pos = holder.getBindingAdapterPosition();
                if (pos != RecyclerView.NO_POSITION) {
                    delegate.onRowPress(pos);
                }
            });
            delegate.mountRow(
                position,
                holder.container,
                currentWidthDp(holder.container),
                delegate.getRowHeightDp(position)
            );
        }

        @Override
        public void onViewRecycled(@NonNull RowHolder holder) {
            holder.container.removeAllViews();
            holder.container.setOnClickListener(null);
            delegate.onRowRecycled(holder.container);
            super.onViewRecycled(holder);
        }
    }
}
