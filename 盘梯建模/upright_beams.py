"""梯梁截面定向：路径=腹板底部外角；高度方向沿世界+Z。"""
from math import hypot

def build_u_profiles(points, side, height=200., width=100., thickness=6., return_start=None):
    if side not in ('inner','outer'):
        raise ValueError('梯梁侧别必须为inner或outer。')
    if height <= 2*thickness or width <= thickness or thickness <= 0:
        raise ValueError('U形截面尺寸无效。')
    # 局部v从腹板外表面底角向上；内外梁仍保持背靠背。
    outline=[(0,height),(width,height),(width,height-thickness),
             (thickness,height-thickness),(thickness,thickness),
             (width,thickness),(width,0),(0,0)]
    sign=-1 if side=='inner' else 1
    profiles=[]
    return_normal=None
    if return_start is not None:
        if return_start != len(points)-2:
            raise ValueError('顶部内折段必须是路径的最后一段。')
        start,end=points[-2:]
        dx,dy=end[0]-start[0],end[1]-start[1]
        length=hypot(dx,dy)
        if length <= 1.e-9:
            raise ValueError('顶部内折段不能为零长度。')
        nx,ny=-dy/length,dx/length
        previous=points[-3]
        # 回折横梁位于平台末端，开口朝平台出口之外。
        # 用平台进入末端的走向选侧，不能用罐径向判定横梁的内外。
        incoming=(start[0]-previous[0],start[1]-previous[1])
        if nx*incoming[0]+ny*incoming[1]<0:
            nx,ny=-nx,-ny
        return_normal=(nx,ny)
    for index,(x,y,z) in enumerate(points):
        radius=hypot(x,y)
        if radius <= 1.e-9:
            raise ValueError('梯梁路径不能通过罐中心轴。')
        nx,ny=x/radius,y/radius
        if return_normal is not None:
            rx,ry=return_normal
            if index==return_start:
                denominator=1+nx*rx+ny*ry
                if denominator <= 1.e-8:
                    raise ValueError('顶部内折转角无法斜接。')
                nx,ny=(nx+rx)/denominator,(ny+ry)/denominator
            elif index>return_start:
                nx,ny=rx,ry
        ux,uy=sign*nx,sign*ny
        profiles.append([(x+u*ux,y+u*uy,z+v) for u,v in outline])
    return profiles
