package com.example.labelMark.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.example.labelMark.domain.sysUser;
import com.example.labelMark.mapper.SysUserMapper;
import com.example.labelMark.service.SysUserService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

/**
 * <p>
 * 服务实现类
 * </p>
 *
 * @author wh
 * @since 2024-04-15
 */
@Service
public class SysUserServiceImpl extends ServiceImpl<SysUserMapper, sysUser> implements SysUserService {
    @Autowired
    private SysUserMapper sysUserMapper;

    @Override
    public int createUser(sysUser user) {
        return sysUserMapper.insert(user);
    }
}