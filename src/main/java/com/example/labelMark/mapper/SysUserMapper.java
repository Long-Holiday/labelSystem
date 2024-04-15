package com.example.labelMark.mapper;

import com.example.labelMark.domain.SysUser;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;

/**
 * <p>
 * Mapper 接口
 * </p>
 *
 * @author wh
 * @since 2024-04-15
 */
@Mapper
public interface SysUserMapper extends BaseMapper<SysUser> {
    @Override
    int insert(SysUser user);
}
