// 关系线：数据里的一条关联（bind）。选中对象的关系加粗并写出说明
import {BaseEdge, EdgeLabelRenderer, getBezierPath} from '@xyflow/react';
import type {Edge, EdgeProps} from '@xyflow/react';

export type RelationEdgeType = Edge<{hot: boolean; tips: string; title: string}, 'relation'>;

export function RelationEdge({sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, markerEnd, data}: EdgeProps<RelationEdgeType>) {
  const [path, labelX, labelY] = getBezierPath({sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition});
  return (
    <>
      <BaseEdge path={path} markerEnd={markerEnd} className={data?.hot ? 'link hot' : 'link'} />
      {data?.hot && data.tips && (
        <EdgeLabelRenderer>
          <div className="link-tip" style={{transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`}}>{data.tips}</div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}
