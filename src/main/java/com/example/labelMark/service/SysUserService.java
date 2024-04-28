package com.example.labelMark.service;

import com.baomidou.mybatisplus.extension.service.IService;
import com.example.labelMark.domain.sysUser;

/**
 * <p>
 * 服务类
 * </p>
 *
 * @author wh
 * @since 2024-04-15
 */
public interface SysUserService extends IService<sysUser> {
    /**
     * 创建用户
     *
     * @param user
     * @return
     */
    int createUser(sysUser user);
}
